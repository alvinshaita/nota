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
    <method name='OpenAllNotes'/>
    <method name='CloseAllNotes'/>
    <method name='OpenGroup'>
      <arg type='s' name='group' direction='in'/>
    </method>
    <method name='OpenGroupOnly'>
      <arg type='s' name='group' direction='in'/>
    </method>
    <method name='OpenNote'>
      <arg type='s' name='note_id' direction='in'/>
    </method>
    <method name='ToggleNote'>
      <arg type='s' name='note_id' direction='in'/>
    </method>
  </interface>
</node>
"""
