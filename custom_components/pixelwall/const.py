"""Constants for the Pixelwall integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "pixelwall"
MANUFACTURER = "Pixelwall"
DASHBOARD_URL = "https://pixelwall.nl/schermen/{id}"

CONF_KEY = "key"

SCAN_INTERVAL = timedelta(seconds=10)

SERVICE_SHOW_MESSAGE = "show_message"
SERVICE_SET_PAGE = "set_page"
SERVICE_DELETE_PAGE = "delete_page"
SERVICE_SET_VALUES = "set_values"
ATTR_PAGE = "page"
ATTR_LAYOUT = "layout"
ATTR_ITEMS = "items"
ATTR_VALUES = "values"
ATTR_DEVICE_ID = "device_id"
ATTR_MESSAGE = "message"
ATTR_TITLE = "title"
ATTR_ICON = "icon"
ATTR_COLOR = "color"
ATTR_DURATION = "duration"

