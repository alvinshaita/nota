"""Shared D-Bus constants for IPC between the main app and the tray process."""

BUS_NAME = "com.github.nota"
OBJECT_PATH = "/com/github/nota"
INTERFACE_NAME = "com.github.nota.Notes"

INTROSPECTION_XML = f"""
<node>
  <interface name='{INTERFACE_NAME}'>
    <method name='LeftClickActivate'/>
    <method name='NewNote'/>
    <method name='ShowSettings'/>
    <method name='Quit'/>
  </interface>
</node>
"""
