########## Surface runoff ##########

# - Function that returns Ch
def Ch_calc(self, pcr, TUr, dg, Zr, tpor, b):
    """
    :param pcr:
    :pcr  type:

    :param TUr:
    :TUr  type:    
    
    :param dg:
    :dg  type:

    :param Zr:
    :Zr  type:    

    :param tpor:
    :tpor  type:  

    :param b:
    :b  type:      

    :returns:
    :rtype: 
    """         
    tur = TUr/(dg*Zr*10) # [%] soil moisture
    Ch = (tur/tpor)**b
    return Ch

# - Function that returns Cper
def Cper_calc(self, pcr, TUw, dg, Zr, S, manning, w1, w2, w3):
    """
    :param pcr:
    :pcr  type:

    :param TUw:
    :TUw  type:    
    
    :param dg:
    :dg  type:

    :param Zr:
    :Zr  type:    

    :param S:
    :S  type:  

    :param manning:
    :manning  type:      

    :param w1:
    :w1  type:   

    :param w2:
    :w2  type:      

    :param w3:
    :w3  type:  

    :returns:
    :rtype: 
    """         
    tuw = TUw/(dg*Zr*10) # [%] soil wilting point
    Cper = w1*(0.02/manning) + w2*(tuw/(1-tuw)) + w3*((S/(10+S)))
    return Cper

# - Function that returns Cimp
def Cimp_calc(self, pcr, ao, ai):
    """
    :param pcr:
    :pcr  type:

    :param ao:
    :ao  type:    
    
    :param ai:
    :ai  type:

    :returns:
    :rtype: 
    """     
    Aimp = ao + ai
    Cimp = (0.09*pcr.exp((2.4*Aimp)))
    return Aimp, Cimp

# - Function that returns Cwp
def Cwp_calc(self, pcr, Aimp, Cper, Cimp):
    """
    :param pcr:
    :pcr  type:

    :param Aimp:
    :Aimp  type:    
    
    :param Cper:
    :Cper  type:

    :param Cimp:
    :Cimp  type:        

    :returns:
    :rtype: 
    """         
    Cwp = (1-Aimp)*Cper+Aimp*Cimp
    return Cwp

# - Function that returns Csr
def Csr_calc(self, pcr, Cwp, P_24, RCD):
    """
    :param pcr:
    :pcr  type:

    :param Cwp:
    :Cwp  type:    
    
    :param P_24:
    :P_24  type:

    :param RCD:
    :RCD  type:        

    :returns:
    :rtype: 
    """          
    Csr = (Cwp*P_24)/(Cwp*P_24 - RCD*Cwp + RCD)
    return Csr

# - Function that returns Surface runoff
def ES_calc(self, pcr, Csr, Ch, prec, I, Ao, ETao):
    """
    :param pcr:
    :pcr  type:

    :param Csr:
    :Csr  type:    
    
    :param Ch:
    :Ch  type:

    :param prec:
    :prec  type:    

    :param I:
    :I  type:  

    :param Ao:
    :Ao  type:      

    :param ETao:
    :ETao  type:   
    
    :returns:
    :rtype: 
    """           
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)
    # condition for positive value for (prec - ETao)
    cond2 = pcr.scalar((prec-ETao) >0)
    
    ES = (Csr*Ch*(prec - I))*(1-cond1) + (prec-ETao)*cond2*cond1
    return ES



