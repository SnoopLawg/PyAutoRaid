#Check time. Cb runs a total of 4 times. (currently 3 times before 10 pm and then one time between 10pm and 4 am)
from datetime import datetime, time

def is_time_between(begin_time=time(22,0), end_time=time(4,00), check_time=None):
    # If check time is not given, default to current UTC time
    check_time = check_time or datetime.now().time()
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

if __name__=='__main__':
    #I want to run a different cb if time is between 10pm and 4 am when script runs
    print(is_time_between(time(22,0), time(4,00)))


