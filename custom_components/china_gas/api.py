"""API client for the China Gas integration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import logging
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    CONF_ACCESS_FROM,
    CONF_ACCESS_TOKEN,
    CONF_BILL_MONTHS,
    CONF_CUST_CODE,
    CONF_CUST_NAME,
    CONF_REFERER,
    CONF_SECRET_KEY,
    CONF_UPDATE_INTERVAL,
    CONF_USER_AGENT,
    CONF_USER_ID,
    CONF_X_MAS_APP_INFO,
    DEFAULT_ACCESS_FROM,
    DEFAULT_BILL_MONTHS,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://zrds.95007.com"
ENDPOINT_TRACK_EVENT = "/tracking/buriedPointEvent/add"
ENDPOINT_CHECK_TOKEN = "/wisdom/auth/checkMasInfo"
ENDPOINT_CUSTOMER_INFO = "/crm_controller/user/findCustInfoByCustCodeAndCustName"
ENDPOINT_MONTHLY_BILLS = "/crm_controller/payfee/getCustomerMoneyList"

CONTENT_TYPE_FORM = "application/x-www-form-urlencoded"
CONTENT_TYPE_JSON = "application/json"


class ChinaGasError(Exception):
    """Base exception for China Gas API errors."""


class ChinaGasAuthError(ChinaGasError):
    """Raised when the configured token is invalid."""


class ChinaGasAccountError(ChinaGasError):
    """Raised when the gas account cannot be found."""


class ChinaGasResponseError(ChinaGasError):
    """Raised when the API response is invalid or unexpected."""


@dataclass(frozen=True)
class ChinaGasAccountConfig:
    """Configuration for a single China Gas account."""

    name: str
    cust_code: str
    cust_name: str
    user_id: str
    access_token: str
    x_mas_app_info: str
    referer: str
    secret_key: str
    access_from: str = DEFAULT_ACCESS_FROM
    user_agent: str = DEFAULT_USER_AGENT
    update_interval: int = 21600
    bill_months: int = DEFAULT_BILL_MONTHS

    @property
    def unique_key(self) -> str:
        """Return a stable key for this account."""
        return f"{self.user_id}_{self.cust_code}"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ChinaGasAccountConfig":
        """Create an account config from config entry data/options."""
        cust_code = str(data[CONF_CUST_CODE]).strip()
        cust_name = str(data[CONF_CUST_NAME]).strip()
        name = str(data.get("name") or f"{cust_code}-{cust_name}").strip()

        return cls(
            name=name,
            cust_code=cust_code,
            cust_name=cust_name,
            user_id=str(data[CONF_USER_ID]).strip(),
            access_token=str(data[CONF_ACCESS_TOKEN]).strip(),
            x_mas_app_info=str(data[CONF_X_MAS_APP_INFO]).strip(),
            referer=str(data[CONF_REFERER]).strip(),
            secret_key=str(data[CONF_SECRET_KEY]).strip(),
            access_from=str(data.get(CONF_ACCESS_FROM) or DEFAULT_ACCESS_FROM).strip(),
            user_agent=str(data.get(CONF_USER_AGENT) or DEFAULT_USER_AGENT).strip(),
            update_interval=int(data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)),
            bill_months=int(data.get(CONF_BILL_MONTHS, DEFAULT_BILL_MONTHS)),
        )


@dataclass
class ChinaGasData:
    """Normalized data for a single China Gas account."""

    customer: dict[str, Any]
    bills: list[dict[str, Any]]
    statistics: dict[str, Any]
    latest_bill: dict[str, Any] | None
    last_update: str
    available: bool = True


class ChinaGasApiClient:
    """Small async client for the China Gas mini-program endpoints."""

    def __init__(self, session: ClientSession, account: ChinaGasAccountConfig) -> None:
        """Initialize the client."""
        self._session = session
        self.account = account

    async def async_fetch_all(self) -> ChinaGasData:
        """Fetch and normalize all account data."""
        try:
            await self.async_track_event()
        except ChinaGasError as err:
            _LOGGER.warning("China Gas initialization request failed: %s", err)

        try:
            await self.async_check_token()
        except ChinaGasAuthError:
            raise
        except ChinaGasError as err:
            _LOGGER.warning("China Gas token check failed; continuing: %s", err)

        customer = await self.async_get_customer_info()

        try:
            bills = await self.async_get_monthly_bills(self.account.bill_months)
        except ChinaGasError as err:
            _LOGGER.warning("Unable to fetch China Gas monthly bills: %s", err)
            bills = []

        statistics = calculate_bill_statistics(bills)
        latest_bill = bills[0] if bills else None

        return ChinaGasData(
            customer=customer,
            bills=bills,
            statistics=statistics,
            latest_bill=latest_bill,
            last_update=datetime.now().astimezone().isoformat(),
        )

    async def async_track_event(self) -> None:
        """Send the initialization/buried-point event."""
        payload = urlencode(
            {
                "appUseType": "0",
                "clickType": "3",
                "eventType": "1",
                "channelType": "0",
                "userId": self.account.user_id,
            }
        )
        data = await self._post(
            ENDPOINT_TRACK_EVENT,
            data=payload,
            content_type=CONTENT_TYPE_FORM,
        )

        if data.get("status") not in (1, "1") or data.get("message") != "请求成功":
            raise ChinaGasResponseError("Initialization request failed")

    async def async_check_token(self) -> None:
        """Check whether the configured token is valid."""
        data = await self._post(
            ENDPOINT_CHECK_TOKEN,
            data={},
            content_type=CONTENT_TYPE_JSON,
            as_json=True,
        )

        if data.get("message") != "token有效":
            raise ChinaGasAuthError("China Gas token is invalid")

    async def async_get_customer_info(self) -> dict[str, Any]:
        """Fetch normalized customer information."""
        payload = self._signed_payload(
            {
                "custCode": self.account.cust_code,
                "custName": self.account.cust_name,
            }
        )
        data = await self._post(
            ENDPOINT_CUSTOMER_INFO,
            data=payload,
            content_type=CONTENT_TYPE_FORM,
        )

        if data.get("status") not in (1, "1") or not isinstance(data.get("data"), dict):
            raise ChinaGasAccountError("China Gas account was not found")

        return normalize_customer(data["data"], self.account)

    async def async_get_monthly_bills(self, months: int) -> list[dict[str, Any]]:
        """Fetch normalized monthly bill information."""
        start_month, end_month = month_range(months)
        payload = self._signed_payload(
            {
                "custCode": self.account.cust_code,
                "custName": self.account.cust_name,
                "startTime": start_month,
                "endTime": end_month,
            }
        )
        data = await self._post(
            ENDPOINT_MONTHLY_BILLS,
            data=payload,
            content_type=CONTENT_TYPE_FORM,
        )

        body = data.get("data") if isinstance(data.get("data"), dict) else data
        if not isinstance(body, dict):
            raise ChinaGasResponseError("Monthly bill response is not an object")

        if body.get("retCode") not in (None, True, "true", "True"):
            raise ChinaGasResponseError("Monthly bill query failed")

        bills = body.get("payGasCheckList") or []
        if not isinstance(bills, list):
            raise ChinaGasResponseError("Monthly bill list is not an array")

        normalized = [normalize_bill(item) for item in bills if isinstance(item, dict)]
        return sorted(
            normalized,
            key=lambda bill: (
                bill.get("record_month_raw") or "",
                bill.get("time_cur_record_raw") or "",
            ),
            reverse=True,
        )

    async def _post(
        self,
        endpoint: str,
        *,
        data: Any,
        content_type: str,
        as_json: bool = False,
    ) -> dict[str, Any]:
        """POST to an endpoint and return JSON."""
        url = f"{BASE_URL}{endpoint}"
        headers = self._headers(content_type)
        timeout = ClientTimeout(total=20)

        try:
            if as_json:
                response_cm = self._session.post(
                    url, json=data, headers=headers, timeout=timeout
                )
            else:
                response_cm = self._session.post(
                    url, data=data, headers=headers, timeout=timeout
                )

            async with response_cm as response:
                text = await response.text()
                if response.status >= 400:
                    raise ChinaGasResponseError(
                        f"China Gas API returned HTTP {response.status}"
                    )
        except TimeoutError as err:
            raise ChinaGasResponseError("China Gas API request timed out") from err
        except ClientError as err:
            raise ChinaGasResponseError("China Gas API request failed") from err
        except UnicodeDecodeError as err:
            raise ChinaGasResponseError("China Gas API response decoding failed") from err

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as err:
            _LOGGER.debug(
                "Invalid China Gas JSON response from %s, length=%s",
                endpoint,
                len(text),
            )
            raise ChinaGasResponseError("China Gas API returned invalid JSON") from err

        if not isinstance(parsed, dict):
            raise ChinaGasResponseError("China Gas API returned an unexpected response")
        return parsed

    def _headers(self, content_type: str) -> dict[str, str]:
        """Build headers for a China Gas request."""
        return {
            "Host": "zrds.95007.com",
            "Connection": "keep-alive",
            "xweb_xhr": "1",
            "accessToken": self.account.access_token,
            "x-mas-app-info": self.account.x_mas_app_info,
            "accessFrom": self.account.access_from,
            "User-Agent": self.account.user_agent,
            "userId": self.account.user_id,
            "Content-Type": content_type,
            "platform": "mp-weixin",
            "Accept": "*/*",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": self.account.referer,
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _signed_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a payload with timestamp and signature."""
        time_stamp = int(datetime.now().timestamp() * 1000)
        raw = f"{self.account.cust_code}{self.account.secret_key}{time_stamp}"
        signature = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return {
            **payload,
            "timeStamp": time_stamp,
            "signature": signature,
        }


def normalize_customer(
    data: dict[str, Any], account: ChinaGasAccountConfig
) -> dict[str, Any]:
    """Normalize customer information from the API."""
    return {
        "cust_code": data.get("custCode") or account.cust_code,
        "cust_name": data.get("custName") or account.cust_name,
        "balance": to_float(data.get("countMoney")),
        "new_balance": to_float(data.get("newCountMoney")),
        "owe_money": first_float(data.get("oweMoney"), data.get("newOweMoney")),
        "qty_balance": to_float(data.get("qtyBalance")),
        "max_gas": to_float(data.get("maxGas")),
        "award_money": first_float(data.get("newAwardMoney"), data.get("awardMoney")),
        "agent_money": first_float(data.get("newAgentMoney"), data.get("agentMoney")),
        "last_record": to_float(data.get("lastRecord")),
        "last_record_time": parse_date(data.get("lastRecordTime")),
        "customer_status": data.get("custStatus"),
        "customer_type": data.get("custType"),
        "meter_status": data.get("feeFlag") or data.get("custStatus"),
        "company": data.get("compName"),
        "address": data.get("address"),
        "mobile": data.get("mobile"),
        "meter_no": data.get("meterNo"),
        "meter_model": data.get("meterFormName") or data.get("meterFormCode"),
        "meter_form_name": data.get("meterFormName"),
        "meter_form_code": data.get("meterFormCode"),
        "meter_seq": data.get("meterSeq"),
        "meter_type": data.get("metertype") or data.get("meterType"),
    }


def normalize_bill(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize one monthly bill item."""
    record_month_raw = value_or_none(data.get("recordMonth"))
    return {
        "cust_code": value_or_none(data.get("custCode")),
        "record_month": parse_month(record_month_raw),
        "record_month_raw": record_month_raw,
        "time_last_record": parse_date(data.get("timeLastRecord")),
        "time_last_record_raw": value_or_none(data.get("timeLastRecord")),
        "last_record": to_float(data.get("lastRecord")),
        "time_cur_record": parse_date(data.get("timeCurRecord")),
        "time_cur_record_raw": value_or_none(data.get("timeCurRecord")),
        "cur_record": to_float(data.get("curRecord")),
        "current_quantity": to_float(data.get("curQty")),
        "receivable": to_float(data.get("receivable")),
        "received": to_float(data.get("received")),
        "total_fee": to_float(data.get("totalFee")),
        "gas_fee": to_float(data.get("gasFee")),
        "later_fee": to_float(data.get("laterFee")),
        "is_pay": value_or_none(data.get("isPay")),
    }


def calculate_bill_statistics(
    bills: list[dict[str, Any]], months: int = 12
) -> dict[str, Any]:
    """Calculate bill statistics for the latest bill months."""
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"usage": 0.0, "fee": 0.0, "bill_count": 0}
    )

    for bill in bills:
        month = bill.get("record_month_raw")
        if not month:
            continue

        grouped[month]["bill_count"] += 1
        if bill.get("current_quantity") is not None:
            grouped[month]["usage"] += float(bill["current_quantity"])
        if bill.get("total_fee") is not None:
            grouped[month]["fee"] += float(bill["total_fee"])

    selected_months = sorted(grouped.keys(), reverse=True)[:months]
    months_count = len(selected_months)

    if months_count == 0:
        return {
            "last_12_months_usage": None,
            "last_12_months_fee": None,
            "average_monthly_usage": None,
            "average_monthly_fee": None,
            "months_count": 0,
            "start_month": None,
            "end_month": None,
            "source_bill_count": 0,
        }

    total_usage = sum(grouped[month]["usage"] for month in selected_months)
    total_fee = sum(grouped[month]["fee"] for month in selected_months)
    source_bill_count = sum(grouped[month]["bill_count"] for month in selected_months)

    chronological = sorted(selected_months)
    return {
        "last_12_months_usage": round(total_usage, 3),
        "last_12_months_fee": round(total_fee, 2),
        "average_monthly_usage": round(total_usage / months_count, 3),
        "average_monthly_fee": round(total_fee / months_count, 2),
        "months_count": months_count,
        "start_month": parse_month(chronological[0]),
        "end_month": parse_month(chronological[-1]),
        "source_bill_count": source_bill_count,
    }


def month_range(months: int) -> tuple[str, str]:
    """Return a safe query month range in YYYYMM format."""
    current = date.today().replace(day=1)
    start = add_months(current, -max(months, DEFAULT_BILL_MONTHS))
    return start.strftime("%Y%m"), current.strftime("%Y%m")


def add_months(value: date, months: int) -> date:
    """Add months to a date clamped to the first day."""
    month_index = value.year * 12 + value.month - 1 + months
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def first_float(*values: Any) -> float | None:
    """Return the first value that can be converted to float."""
    for value in values:
        converted = to_float(value)
        if converted is not None:
            return converted
    return None


def to_float(value: Any) -> float | None:
    """Convert API values to float."""
    value = value_or_none(value)
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def value_or_none(value: Any) -> str | None:
    """Normalize empty API values to None."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def parse_date(value: Any) -> str | None:
    """Parse YYYYMMDD or YYYY-MM-DD to YYYY-MM-DD."""
    raw = value_or_none(value)
    if raw is None:
        return None
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return raw


def parse_month(value: Any) -> str | None:
    """Parse YYYYMM to YYYY-MM."""
    raw = value_or_none(value)
    if raw is None:
        return None
    if len(raw) == 6 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}"
    return raw
