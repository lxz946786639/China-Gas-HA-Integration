"""Sensor platform for China Gas."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ChinaGasData
from .const import DATA_COORDINATORS, DOMAIN, MANUFACTURER
from .coordinator import ChinaGasDataUpdateCoordinator

CURRENCY_CNY = "CNY"
UNIT_CUBIC_METERS = "m³"
DEVICE_CLASS_DATE = getattr(SensorDeviceClass, "DATE", "date")
DEVICE_CLASS_GAS = getattr(SensorDeviceClass, "GAS", "gas")
DEVICE_CLASS_MONETARY = getattr(SensorDeviceClass, "MONETARY", "monetary")
STATE_CLASS_MEASUREMENT = getattr(SensorStateClass, "MEASUREMENT", "measurement")
STATE_CLASS_TOTAL_INCREASING = getattr(
    SensorStateClass, "TOTAL_INCREASING", "total_increasing"
)


@dataclass(frozen=True, kw_only=True)
class ChinaGasSensorEntityDescription(SensorEntityDescription):
    """Description for a China Gas sensor."""

    value_fn: Callable[[ChinaGasData], Any]
    attrs_fn: Callable[[ChinaGasData], dict[str, Any]] | None = None


def _customer_value(key: str) -> Callable[[ChinaGasData], Any]:
    return lambda data: data.customer.get(key)


def _latest_bill_value(key: str) -> Callable[[ChinaGasData], Any]:
    return lambda data: data.latest_bill.get(key) if data.latest_bill else None


def _statistics_value(key: str) -> Callable[[ChinaGasData], Any]:
    return lambda data: data.statistics.get(key)


def _latest_bill_attrs(data: ChinaGasData) -> dict[str, Any]:
    return dict(data.latest_bill or {})


def _statistics_attrs(data: ChinaGasData) -> dict[str, Any]:
    return {
        "months_count": data.statistics.get("months_count"),
        "start_month": data.statistics.get("start_month"),
        "end_month": data.statistics.get("end_month"),
        "source_bill_count": data.statistics.get("source_bill_count"),
    }


def _balance_attrs(data: ChinaGasData) -> dict[str, Any]:
    customer = data.customer
    return {
        "cust_code": customer.get("cust_code"),
        "cust_name": customer.get("cust_name"),
        "company": customer.get("company"),
        "address": customer.get("address"),
        "mobile": customer.get("mobile"),
        "meter_no": customer.get("meter_no"),
        "meter_form_name": customer.get("meter_form_name"),
        "meter_form_code": customer.get("meter_form_code"),
        "meter_seq": customer.get("meter_seq"),
        "meter_type": customer.get("meter_type"),
        "last_record": customer.get("last_record"),
        "last_record_time": customer.get("last_record_time"),
        "customer_status": customer.get("customer_status"),
        "last_update": data.last_update,
    }


def _gas_meter_attrs(data: ChinaGasData) -> dict[str, Any]:
    customer = data.customer
    return {
        "meterNo": customer.get("meter_no"),
        "metertype": customer.get("meter_type"),
        "meterFormCode": customer.get("meter_form_code"),
        "meterSeq": customer.get("meter_seq"),
    }


def _monthly_bills_attrs(data: ChinaGasData) -> dict[str, Any]:
    return {
        "bills": data.bills,
        "bill_count": len(data.bills),
    }


SENSORS: tuple[ChinaGasSensorEntityDescription, ...] = (
    ChinaGasSensorEntityDescription(
        key="balance",
        translation_key="balance",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("balance"),
        attrs_fn=_balance_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="new_balance",
        translation_key="new_balance",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("new_balance"),
    ),
    ChinaGasSensorEntityDescription(
        key="owe_money",
        translation_key="owe_money",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("owe_money"),
    ),
    ChinaGasSensorEntityDescription(
        key="latest_bill_fee",
        translation_key="latest_bill_fee",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_latest_bill_value("total_fee"),
        attrs_fn=_latest_bill_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="latest_bill_usage",
        translation_key="latest_bill_usage",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=UNIT_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_latest_bill_value("current_quantity"),
        attrs_fn=_latest_bill_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="latest_bill_month",
        translation_key="latest_bill_month",
        value_fn=_latest_bill_value("record_month"),
        attrs_fn=_latest_bill_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="last_12_months_usage",
        translation_key="last_12_months_usage",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=UNIT_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_statistics_value("last_12_months_usage"),
        attrs_fn=_statistics_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="last_12_months_fee",
        translation_key="last_12_months_fee",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_statistics_value("last_12_months_fee"),
        attrs_fn=_statistics_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="average_monthly_usage",
        translation_key="average_monthly_usage",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=UNIT_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_statistics_value("average_monthly_usage"),
        attrs_fn=_statistics_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="average_monthly_fee",
        translation_key="average_monthly_fee",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_statistics_value("average_monthly_fee"),
        attrs_fn=_statistics_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="last_record",
        translation_key="last_record",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=UNIT_CUBIC_METERS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        value_fn=_customer_value("last_record"),
    ),
    ChinaGasSensorEntityDescription(
        key="last_record_date",
        translation_key="last_record_date",
        device_class=DEVICE_CLASS_DATE,
        value_fn=lambda data: parse_ha_date(data.customer.get("last_record_time")),
    ),
    ChinaGasSensorEntityDescription(
        key="qty_balance",
        translation_key="qty_balance",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=UNIT_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("qty_balance"),
    ),
    ChinaGasSensorEntityDescription(
        key="max_gas",
        translation_key="max_gas",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=UNIT_CUBIC_METERS,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("max_gas"),
    ),
    ChinaGasSensorEntityDescription(
        key="award_money",
        translation_key="award_money",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("award_money"),
    ),
    ChinaGasSensorEntityDescription(
        key="agent_money",
        translation_key="agent_money",
        device_class=DEVICE_CLASS_MONETARY,
        native_unit_of_measurement=CURRENCY_CNY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=_customer_value("agent_money"),
    ),
    ChinaGasSensorEntityDescription(
        key="company",
        translation_key="company",
        value_fn=_customer_value("company"),
    ),
    ChinaGasSensorEntityDescription(
        key="address",
        translation_key="address",
        value_fn=_customer_value("address"),
    ),
    ChinaGasSensorEntityDescription(
        key="mobile",
        translation_key="mobile",
        value_fn=_customer_value("mobile"),
    ),
    ChinaGasSensorEntityDescription(
        key="gas_meter",
        translation_key="gas_meter",
        value_fn=_customer_value("meter_form_name"),
        attrs_fn=_gas_meter_attrs,
    ),
    ChinaGasSensorEntityDescription(
        key="customer_type",
        translation_key="customer_type",
        value_fn=_customer_value("customer_type"),
    ),
    ChinaGasSensorEntityDescription(
        key="customer_status",
        translation_key="customer_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_customer_value("customer_status"),
    ),
    ChinaGasSensorEntityDescription(
        key="meter_status",
        translation_key="meter_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_customer_value("meter_status"),
    ),
    ChinaGasSensorEntityDescription(
        key="monthly_bills",
        translation_key="monthly_bills",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_latest_bill_value("record_month"),
        attrs_fn=_monthly_bills_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up China Gas sensors."""
    coordinator: ChinaGasDataUpdateCoordinator = hass.data[DOMAIN][DATA_COORDINATORS][
        entry.entry_id
    ]
    async_add_entities(
        ChinaGasSensor(coordinator, entry, description) for description in SENSORS
    )


class ChinaGasSensor(CoordinatorEntity, SensorEntity):
    """China Gas sensor entity."""

    entity_description: ChinaGasSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ChinaGasDataUpdateCoordinator,
        entry: ConfigEntry,
        description: ChinaGasSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        account = coordinator.api.account
        self._attr_unique_id = (
            f"{DOMAIN}_{account.user_id}_{account.cust_code}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account.unique_key)},
            manufacturer=MANUFACTURER,
            name=account.name,
            model=coordinator.data.customer.get("meter_form_name")
            or coordinator.data.customer.get("meter_model"),
            serial_number=coordinator.data.customer.get("meter_no"),
        )
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


def parse_ha_date(value: Any) -> date | None:
    """Parse an ISO date string for Home Assistant date sensors."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
