from datetime import datetime, time

def is_time_between(begin_time=time(22,0), end_time=time(4,00), check_time=None):
    # If check time is not given, default to current UTC time
    check_time = check_time or datetime.now().time()
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

if __name__=='__main__':
    #Original test case from OP
    print(is_time_between(time(22,0), time(4,00),))


