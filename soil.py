########## Lateral Flow ##########
def LF_calc(pcr, self, f, Kr, TUr, TUsat):
    LF = f*Kr*((TUr/TUsat)**2)
    return LF

########## Recharge ##########
def REC_calc(pcr, self, f, Kr, TUr, TUsat):
    REC = (1-f)*Kr*((TUr/TUsat)**2)
    return REC    

########## Base Flow ##########
def EB_calc(pcr, self, EB_prev, alfaS, REC, TUs, EB_lim):
    # limit condition for base flow
    cond = pcr.scalar(TUs > EB_lim)
    EB = ((EB_prev*((pcr.exp(1))**-alfaS))+(1-((pcr.exp(1))**-alfaS))*REC)*cond
    return EB

########## Soil Balance ##########
# First soil layer
def TUr_calc(pcr, self, TUrprev, P, I, ES, LF, REC, ETr, Ao, Tsat):
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
def TUs_calc(pcr, self, TUsprev, REC, EB):
    # soil balance
    balance = TUsprev + REC - EB
    TUs = balance
    return TUs