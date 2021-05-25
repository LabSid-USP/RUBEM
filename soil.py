# coding=utf-8

########## Lateral Flow ##########
def LF_calc(self, pcr, f, Kr, TUr, TUsat):
    """
    :param pcr:
    :pcr  type:

    :param f:
    :f  type:    
    
    :param TUr:
    :TUr  type:

    :param TUsat:
    :TUsat  type:    
    
    :returns:
    :rtype: 
    """         
    LF = f*Kr*((TUr/TUsat)**2)
    return LF

########## Recharge ##########
def REC_calc(self, pcr, f, Kr, TUr, TUsat):
    """
    :param pcr:
    :pcr  type:

    :param f:
    :f  type:   

    :param Kr:
    :Kr  type:  
    
    :param TUr:
    :TUr  type:

    :param TUsat:
    :TUsat  type:    
    
    :returns:
    :rtype: 
    """          
    REC = (1-f)*Kr*((TUr/TUsat)**2)
    return REC    

########## Base Flow ##########
def EB_calc(self, pcr, EB_prev, alfaS, REC, TUs, EB_lim):
    """
    :param pcr:
    :pcr  type:

    :param EB_prev:
    :EB_prev  type:   

    :param alfaS:
    :alfaS  type:  
    
    :param REC:
    :REC  type:

    :param TUs:
    :TUs  type: 

    :param EB_lim:
    :EB_lim  type:    
    
    :returns:
    :rtype: 
    """         
    # limit condition for base flow
    cond = pcr.scalar(TUs > EB_lim)
    EB = ((EB_prev*((pcr.exp(1))**-alfaS))+(1-((pcr.exp(1))**-alfaS))*REC)*cond
    return EB

########## Soil Balance ##########
# First soil layer
def TUr_calc(self, pcr, TUrprev, P, I, ES, LF, REC, ETr, Ao, Tsat):
    """
    :param pcr:
    :pcr  type:

    :param TUrprev:
    :TUrprev  type:   

    :param P:
    :P  type:  
    
    :param I:
    :I  type:

    :param ES:
    :ES  type: 

    :param LF:
    :LF  type: 

    :param REC:
    :REC  type:  

    :param ETr:
    :ETr  type:  

    :param Ao:
    :Ao  type:  

    :param Tsat:
    :Tsat  type:              
    
    :returns:
    :rtype: 
    """           
    # condition for pixel of water, if Ao different of 1 (not water)
    condw1 = pcr.scalar(Ao != 1)
    # soil balance
    balance = TUrprev + P - I - ES - LF - REC - ETr    
    # condition for positivie balance
    cond = pcr.scalar(balance>0)    
    # if balance is negative TUR = 0, + if pixel is water, TUR = TUsat
    TUr = (balance*cond)*condw1 + Tsat*(1-condw1)
    return TUr

# Second soil layer
def TUs_calc(self, pcr, TUsprev, REC, EB):
    """
    :param pcr:
    :pcr  type:

    :param TUsprev:
    :TUsprev  type:   

    :param REC:
    :REC  type:  
    
    :param EB:
    :EB  type:

    :returns:
    :rtype: 
    """            
    # soil balance
    balance = TUsprev + REC - EB
    TUs = balance
    return TUs