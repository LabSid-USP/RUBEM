# coding=utf-8
from datetime import datetime
from calendar import monthrange

# Calculation of number of months (steps) based on the start and end dates of simulation
def totalSteps(startDate, endDate):
    """Get the number of months between start and end dates

    :param startDate: Start date.
    :startDate type: str

    :param startDate: End date.
    :startDate type: str

    :return: First step, Last step and Number of months between start and end dates
    :rtype: tuple(int, int ,int)
    """
    start = datetime.strptime(startDate ,'%d/%m/%Y')
    end = datetime.strptime(endDate ,'%d/%m/%Y')
    assert end > start, "End date must be greater than start date"
    nTimeSteps = (end.year - start.year)*12 + (end.month - start.month)
    lastTimeStep = nTimeSteps
    # PCRaster: first timestep argument of DynamicFramework must be > 0
    firstTimestep = 1  
    return (firstTimestep, lastTimeStep, nTimeSteps)

# Calculation of number of days in the month from timestep (for flow conversion from mm to m3/s)
def daysOfMonth(startDate, timestep):
    """
    :param startDate: Start date.
    :startDate  type: str

    :param timestep:
    :timestep  type: int

    :returns: Days of month.
    :rtype: int        
    """     
    sourcedate = datetime.strptime(startDate,'%d/%m/%Y')
    month = sourcedate.month -2 + timestep
    year = sourcedate.year + month // 12
    month = (month % 12) +1
    days = monthrange(year,month)[1]
    return days