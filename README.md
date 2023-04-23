# PySerialSMS

Python support for Serial SMS send/receive with listener for Raspberry Pi

Supports Sierra Wireless AirPrime MC7700 and any modem with compatible serial capabilities. 

* May need to edit to fit your message parsing needs.

* Requires PySerial
#
#
#
#
Systemctl settings to allow log file:
#

sudo nano /etc/systemd/system/SerialSMS.service
####

[Unit]
Description=Serial SMS over LTE modem
After=multi-user.target
StartLimitIntervalSec=2
[Service]
Type=simple
Restart=always
RestartSec=1
User=root
ExecStart=python -u /dir/SerialSMS.py &

[Install]
WantedBy=multi-user.target
  
####

systemctl start SerialSMS.service
systemctl enable SerialSMS.service
systemctl daemon reload
#
#
#  
Example:
#
#
sersms = SerialSMS(mynum, '/dev/ttyUSB2', log_file=lf)

while True:
	incoming_sms = sersms.message_listener()      
	if incoming_sms != None:
		sersms.send_sms(incoming_sms.sender, incoming_sms.message)
