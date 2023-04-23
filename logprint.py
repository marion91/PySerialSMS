import sys
import pathlib

class LogPrint():
    def __init__(self, log_filename):
        self.def_print = print   
        self.log_filename = log_filename
        if not pathlib.Path(log_filename).is_file():
            self.f = open(log_filename, 'w')
            self.f.close()

    def print_log(self, string):
        if not pathlib.Path(self.log_filename).is_file():
            self.f = open(self.log_filename, 'w')
        else:
            self.f = open(self.log_filename, 'a')
        self.f.writelines(string)
        print(string)
        if self.f != None:
            self.f.close()  


        
            