i got it connected by 

# Step 1: allow internet passthrough for your wifi adapter
- ensure your usb to ethernet connector is connected to the laptop and connected DIRECTLY into the orange pi
- start menu > ncpa.cpl
- right click wifi > properties > sharing tab > Allow other network users...
    - if already enabled, disable, and re-enable
- 

# Step 2: Clear the Windows ARP Cache
PS C:\windows\system32> arp -d *

# Step 3: Find the Direct IP Address
PS C:\windows\system32> arp -a | Select-String "192.168.137"

Interface: 192.168.137.1 --- 0x8
  192.168.137.190       d2-45-38-09-f5-44     dynamic


# Connect to PI's direct IP address:

> ssh pi@192.168.137.190

# Final step
Select wifi adapter in control panel, properties, sharing tab, disable "Allow other network users..."
You can now reconnect to the robot using the usual method.