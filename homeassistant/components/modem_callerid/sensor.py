"""A sensor for incoming calls using a USB modem that supports caller ID."""
from __future__ import annotations

import logging

from phone_modem import PhoneModem

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP, STATE_IDLE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_platform

from .const import CID, DATA_KEY_API, DOMAIN, ICON, SERVICE_REJECT_CALL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Modem Caller ID sensor."""
    api = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]
    async_add_entities(
        [
            ModemCalleridSensor(
                api,
                entry.title,
                entry.data[CONF_DEVICE],
                entry.entry_id,
            )
        ]
    )

    async def _async_on_hass_stop(event: Event) -> None:
        """HA is shutting down, close modem port."""
        if hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]:
            await hass.data[DOMAIN][entry.entry_id][DATA_KEY_API].close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_hass_stop)
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_REJECT_CALL, {}, "async_reject_call")
    _LOGGER.warning(
        "Calling reject_call service is deprecated and will be removed after 2022.4; "
        "A new button entity is now available with the same function "
        "and replaces the existing service"
    )


class ModemCalleridSensor(SensorEntity):
    """Implementation of USB modem caller ID sensor."""

    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(
        self, api: PhoneModem, name: str, device: str, server_unique_id: str
    ) -> None:
        """Initialize the sensor."""
        self.device = device
        self.api = api
        self._attr_name = name
        self._attr_unique_id = server_unique_id
        self._attr_native_value = STATE_IDLE
        self._attr_extra_state_attributes = {
            CID.CID_TIME: 0,
            CID.CID_NUMBER: "",
            CID.CID_NAME: "",
        }

    async def async_added_to_hass(self) -> None:
        """Call when the modem sensor is added to Home Assistant."""
        self.api.registercallback(self._async_incoming_call)
        await super().async_added_to_hass()

    @callback
    def _async_incoming_call(self, new_state: str) -> None:
        """Handle new states."""
        self._attr_extra_state_attributes = {}
        if self.api.cid_name:
            self._attr_extra_state_attributes[CID.CID_NAME] = self.api.cid_name
        if self.api.cid_number:
            self._attr_extra_state_attributes[CID.CID_NUMBER] = self.api.cid_number
        if self.api.cid_time:
            self._attr_extra_state_attributes[CID.CID_TIME] = self.api.cid_time
        self._attr_native_value = self.api.state
        self.async_write_ha_state()

    async def async_reject_call(self) -> None:
        """Reject Incoming Call."""
        await self.api.reject_call(self.device)
