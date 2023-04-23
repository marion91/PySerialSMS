import serial
from serial import *
import time
import sys
import os
import logprint

mynum = "+15199885809"
safe_start = True

lf_name = __file__.replace(".py", "")
print(lf_name)

class SerialSMS():

    def __init__(self, my_phone_number, port="/dev/ttyS0", verbose=1, log_file=True, log_filename=lf_name +"output.txt"):  
        global print
        self.AT_OK = "\r\nOK\r\n"                #Expected AT-Responses
        self.AT_MSG_INPUT= ">"
        self.AT_ERROR = "\r\nERROR\r\n"
        self.my_phone_number = my_phone_number
        self.port = port
        self.verbose = verbose
        self.log_file = log_file
        self.log_filename = log_filename
 
        if self.log_file:
            self.log_print = logprint.LogPrint(self.log_filename)
            def print(string):
                self.log_print.print_log(string)
        print("###################  START  ########################")
        print("\nConnecting to modem...\n" + 
            str(time.perf_counter()) + 
            "s\n")
        
        while True:
            try:     
                self.ser=serial.Serial(self.port,115200,bytesize=EIGHTBITS,parity=PARITY_NONE,stopbits=STOPBITS_ONE,timeout=5, xonxoff=0, rtscts=0) # Change to your port '/dev/ttyUSB2'
            except:
                print("\nError connecting to modem...")
                time.sleep(2)
                continue
            break
        print(self.ser)

        self.ser.close()
        if not self.ser.is_open:
            self.ser.open()

        print("\n")
        self.send_AT("\x1b\x1b\x1b")                             # <ESC> x3 to reset input and cancel any previously interrupted sms message writes. Has no effect if not needed.
        self.buffer_waiting()                                    # Read buffer and discard result
        self.clear_messages("ALL")                               # Discard any unread messages. Enabled for command-based operation.
                                                                 # ***** SIM WILL NOT RECEIVE MESSAGES IF STORAGE FULL. STORE MESSAGES ON HOST DEVICE ********
        
        self.send_AT("AT+CCLK?", self.AT_OK,verbose=1)             # Request time
        self.send_AT("at+creg=1", self.AT_OK)                         # Register on network
        self.send_AT("at+cmgf=1", self.AT_OK)
        self.send_AT("At+cnmi=2,\"1\",\"0\",\"1\",\"0\"", self.AT_OK) # Set message notification mode to notify on incoming message (check your modem's AT-Command reference guide). Quotes added due to errors
        
        if self.send_sms(self.my_phone_number, "Starting") != True:    # Attempt first send while still accepting incoming messages
            self.message_listener()
        else:
            safe_start = False
        
        if safe_start:
            sys.exit()

        if self.verbose == 1:
            verbose = 0

#--------------------------------------------------------------------------------------------------

    class sms_message():
        def __init__(self, data, message_type=0, verbose=0):       # message_type=0 : SMS  ; message_type=1 : MMS
            self.verbose=verbose
            self.raw_data = data
            self.message_type = message_type
            self.AT_response = "<AT_response>"
            self.index = "<index>"
            self.status = "<status>"
            self.sender = "<sender>"
            self.toa = "<toa>"
            self.timestamp = "<timestamp>"
            self.delivery = "<delivery>"
            self.raw_message = bytes(0x0)
            self.message = "<message>"

            self.parse_sms(self.raw_data)
            self.parse_sender(self.AT_response)


        def parse_sender(self, data):
            data = data.replace("\"", "")
            self.index = data.partition(",")[0]
            data = data.partition(",")[2]
            self.status = data.partition(",")[0]
            data = data.partition(",")[2]
            self.sender = data.partition(",")[0]
            data = data.partition(",")[2]
            if data.find(",") == 0:
                self.timestamp = data.partition(",,")[2]
            else: 
                self.toa = data.partition(",")[0]
                data = data.partition(",")[2]
                self.timestamp = data.partition(",")[2]
            
            self.timestamp = data.partition("-")[0]

        def parse_sms(self, data):
            datastr = bytes.decode(data, "utf-8")               # Decode response locally
            msg_header = datastr.partition("+CMGL:")[1]
            msg_info = datastr.partition(msg_header)[2]             # Separate SENDER INFO from response

            if msg_header.find("+CMGL:") < 0:               # Check for New Message header and parse quality. Guarantees next line is MESSAGE DATA
                return False    
            
            msg_data = msg_info.partition("\r\n")[2]             # Separate MESSAGE DATA from response
            msg_info = msg_info.partition("\r\n")[0]
            msg_data = msg_data.partition("\r\n\r\nOK\r\n")[0]  # Remove trailing line breaks -and- OK AT-Response from MESSAGE DATA
            self.AT_response = msg_info
            if self.verbose:
                print(self.AT_response)
            
            self.raw_message = bytes(msg_data, 'utf-8')
            msg_data = msg_data.replace("\r", "")               # Remove carriage returns from MESSAGE DATA
            self.message = msg_data       
            return True
        
#-----V--AT-COMMUNICATION--V-----------------------------------------------------------------------------------------

    def waitRep(self, expected="", verbose=0):             # Wait for reply
        start_timeout = time.perf_counter()
        response = bytes(0x0)

        if len(expected) == 0:
            return True
        
        while self.ser.out_waiting > 0:                                                          # Wait for DATA-OUT w/timeout              
            if time.perf_counter() > start_timeout + self.ser.timeout:
                start_timeout = time.perf_counter()
                break
            pass
        
        while self.ser.in_waiting == 0:
            if time.perf_counter() > start_timeout + self.ser.timeout:                           # Wait for DATA-IN w/timeout
                start_timeout = time.perf_counter()
                break
            pass

        while bytes.decode(response, 'utf-8').find(bytes.decode(expected,'utf-8')) < 0:     # Wait for expected response. Responses usually end with "OK" 
            if time.perf_counter() > start_timeout + self.ser.timeout:
                start_timeout = time.perf_counter()
                break
            response += self.ser.read()

            if bytes.decode(response, 'utf-8').endswith("ERROR\r\n"):                       # Break for ERROR response
                break
            if bytes.decode(response, 'utf-8').find(self.AT_MSG_INPUT) >= 0 and bytes.decode(expected,'utf-8') != self.AT_MSG_INPUT:      # If MESSAGE STOP received while not sending SMS, send <ESC> x3
                self.ser.write(b'\x1b\x1b\x1b')                                                  
                return False 
            
        response_str = bytes.decode(response, 'utf-8')
        
        if len(bytes.decode(expected,'utf-8')) <= 0:                                        # Expected Response = "" :  Skip Success/Fail
            if self.verbose or verbose:
                print("Response: " + response_str + "\n")
            return " "
        
        else:
            if response_str.find(bytes.decode(expected,'utf-8')) >= 0:                      # Expected Response = "OK/>/ERROR" : Success/Fail
                response_str.strip("\r\n")
                if self.verbose or verbose:
                    print("\n\nSuccess!")
                    print("Response: " + response_str + "\n")
                return response
            else:
                if self.verbose or verbose:    
                    print("\n\nException: ")
                    print("Response: " + response_str + "\n")
                return False
        
        
    def send_AT(self, bytestr, expectedstr="", msgstop=False, verbose=0):     # Message, Expected Response, and Message Stop flag. Expected Response is the same for almost everything except entering message data
        self.ser.flush()
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        
        if msgstop == False:
            bytestr = bytestr + '\r'         # "\r" to submit most AT-Commands
            sleep_time = 0.5
        else:
            bytestr = bytestr + '\x1a'       # <CTRL+Z> line ending. "\r" and "\n" are treated as part of the MESSAGE DATA
            sleep_time = 1

        bytestr = bytes(bytestr, 'utf-8')
        expected = bytes(expectedstr, 'utf-8')
        attempts = 0
        
        while True:
            if attempts >= 5:
                return False
            if self.verbose or verbose:
                print("Sending AT: " + bytestr.decode('utf-8').strip("\r\n"))

            if not self.ser.is_open:
                self.ser.open()

            time.sleep(sleep_time)            # Delay required before and after transmitting commands. Can be up to 1 second for MESSAGE DATA. Check your modem's manual
            self.ser.write(bytestr)
            time.sleep(sleep_time)
            
            response = self.waitRep(expected, verbose= self.verbose | verbose)
            if response != False:
                if bytes(response).decode('utf-8').endswith("ERROR\r\n") == False:                 # Check for ERROR AT-response
                    break
                else:
                    if msgstop and bytes(response).decode('utf-8').endswith("ERROR\r\n") == True:     # Abort retry if sending message data. Must start over from initial SEND MESSAGE command       
                        return False
                
            attempts += 1
        
        return response
    
    #--------V--MESSAGE MANAGEMENT--V--------------------------------------------------------------------------------------            

    def send_sms(self, out_number, message, mms=False):
        attempts = 0
        if not self.ser.is_open:
            self.ser.open() 

        while self.send_AT("at+creg=1", self.AT_OK) == False:                     # Check network connection
            self.message_listener()

        if mms:                                         # Set GSM/SMS mode
                self.send_AT("at+cmgf=1", self.AT_OK)
                self.send_AT("at+cmms=2", self.AT_OK)
        else:

                self.send_AT("at+cmgf=1", self.AT_OK)
        
        message_list = []
        while len(message) >= 160:
            message_list.append(message[0 : 159])
            message = message[159 : len(message) - 1]

        while attempts < 5 and len(message_list) == 0:
            print("------------------------------------>>>>>>>>>>\n")
            print("Sending SMS:\n\n" + message)
            
            if self.send_AT("at+cmgs=\"" + out_number + "\"", self.AT_MSG_INPUT) != False:
                if self.send_AT(message, self.AT_OK, True) != False:
                    print("\nSuccess!")
                    print("\n------------------------------------>>>>>>>>>>\n")
                    return True
        while attempts < 5 and len(message_list) > 0:
            print("------------------------------------>>>>>>>>>>\n")
            print("Sending SMS:\n\n" + message_list[0])
            
            if self.send_AT("at+cmgs=\"" + out_number + "\"", self.AT_MSG_INPUT) != False:
                if self.send_AT(message_list[0], self.AT_OK, True) != False:
                    print("\nSuccess!")
                    print("\n------------------------------------>>>>>>>>>>\n")
                    message_list.pop(0)
                    if len(message_list) == 0:
                        self.send_AT("at+cmms=0", self.AT_OK)
                        return True
            attempts += 1
        print("\nFailed...")
        print("------------------------------------>>>>>>>>>>\n")
        self.send_AT("at+cmms=0", self.AT_OK)
        return False
        

    def check_message(self):
        if not self.ser.is_open:
            self.ser.open()

        self.send_AT("at+cmgf=1", self.AT_OK)                         # Enable SMS mode

        response = self.send_AT("at+cmgl", self.AT_OK)                # +cmgl (lower case) response = response is NO SMS MESSAGE
        response_str = bytes.decode(response, 'utf-8')

        if response_str.find("+CMGL:") >= 0:                          # +CMGL (upper case) response = response is SMS MESSAGE
            incoming_sms = self.sms_message(response)
            timestamp = incoming_sms.timestamp.partition(",")[2]
            #timestamp = timestamp.partition(",")[0]
            print("\n------------------------------------<<<<<<<<<\n")
            print("\n"
                + timestamp 
                +" | New Message from " 
                + incoming_sms.sender 
                + ":\n\n" 
                + incoming_sms.message 
                + "\n\n" 
                )
            print("------------------------------------<<<<<<<<<\n")

            return incoming_sms
        else:
            return None


    def clear_messages(self, status):
        statnum = status
        if type(status) == str:
            if status == "READ":
                statnum = 1
            elif status == "READ_SENT":
                statnum = 2
            elif status == "READ_SENT_UNSENT":
                statnum = 3
            elif status == "ALL":
                statnum = 4         
        #else:
        #    statnum = status

        response = self.send_AT("at+cmgd=?", self.AT_OK)                          # Check for messages in storage
        if response != False:
            check_msg = bytes.decode(response, "utf-8").find("()")                # +CMGD: (),(0-4)               = No messages
        if check_msg < 0:                                                         # +CMGD: (0,1,2),(0-4)          = 3 messages (<index>, <index>, <index>)
            self.send_AT("at+cmgd=0," + str(statnum), self.AT_OK)                 # AT+CMGD=0,3                   = "3": Ignore INDEX and delete 3(2(1(READ), SENT,) UNSENT) or 4(ALL) messages
                                                                                  # AT+CMGD=3,0                   = "3": Ignore STATUS and delete INDEX 3

#------V--INCOMING MESSAGE LISTENER--V----------------------------------------------------------------------------------------

    def buffer_waiting(self):
        in_buf = bytes(0x0)
        while self.ser.in_waiting > 0 and len(in_buf) < 160:             # Listen to incoming buffer and collect data if available
            in_buf += self.ser.read()
        if len(in_buf) > 0:
            in_buf = in_buf.decode("utf-8")        # Decode incoming strings and encode outgoing strings to utf-8
            if in_buf.find("+CNMI"):               # Check incoming data for message notification header 
                if self.verbose:
                    print(in_buf)
                return True
            else:
                return False
            
    def message_listener(self):
        if self.buffer_waiting():
            incoming_sms = self.check_message()
            incoming_sms_list = []
            while incoming_sms != None:
                self.clear_messages("READ_SENT_UNSENT")
                incoming_sms_list.append(incoming_sms)
                incoming_sms = self.check_message()
            return incoming_sms_list
             
#-------V--IMPLEMENTATION--V---------------------------------------------------------------------------------------

    def echo(self):        
            incoming_sms = self.message_listener()      
            if incoming_sms != None:
                #YourMessageHandler(incoming_sms)
                self.send_sms(incoming_sms.sender, incoming_sms.message)



if __name__ == '__main__':  
    
    sersms = SerialSMS(mynum, '/dev/ttyUSB2')
    while True:
        sersms.echo()




