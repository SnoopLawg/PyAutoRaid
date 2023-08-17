import logging

logging.basicConfig(filename='Logging.log',format='%(levelname)s:%(message)s', encoding='utf-8', level=logging.DEBUG)

def Log_start(func="???"):
    if func=="???":
        logging.warning("LS Function not passed as parameter to log")
    else:
        logging.info(f' Starting {func}')

def Log_finish(func="???"):
    if func=="???":
        logging.warning(" LF Function not passed as parameter to log")
    else:
        logging.info(f' Finishing {func}')
def Erase_Log():
    with open('Logging.log', 'w'):
        pass
def Throw_log_error(func="???"):
    if func=="???":
        logging.warning(" LF Function not passed as parameter to log")
    else:
        logging.error(f'{func}')
def Log_info(func=""):
    if func=="":
        logging.info("----------------------------------")
    else:
        logging.info(f'{func}')

if __name__ == '__main__':
    Erase_Log()
    Log_start()
    Log_finish()
    Throw_log_error()
    Log_info()