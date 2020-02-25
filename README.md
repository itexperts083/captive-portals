# captive-portals

# Features
Provides web UI for testing and configuring WiFi
Mobile and desktop devices prompt the "Login to network" window/notification
Custom setting and helper functions to enable/disable Captive Portal
RPC endpoint for setting and testing wifi credentials (can be used without captive portal)
Unminified and non-gzipped files are only 14.2kb total in size ( wifi_portal.css - 3kb, wifi_portal.html - 1.45kb, wifi_portal.js - 9.67kb )
Minified and gzipped files are only 3.26kb total in size ( wifi_portal.min.css.gz - 735b, wifi_portal.html.gz - 561b, wifi_portal.min.js.gz - 2kb )
Displays a dropdown of available networks to connect to
Validates user provided SSID and Password
Uses gzipped data for small filesize and fast loading (see dev below for using/customizing files)
Save/Copy SSID and Password to STA 1 (wifi.sta) configuration after succesful test
Reboot after sucesful SSID/Password test (after saving files)
