# coding=utf-8

########## Evapotranspiration Module ##########

# - Function that returns Ks for evapotranspiration of vegetated area
def Ks_calc(self, pcr, TUr, TUw, TUcc):
    """
    :param pcr:
    :pcr  type:

    :param TUr:
    :TUr  type:    
    
    :param TUw:
    :TUw  type:

    :param TUcc:
    :TUcc  type:    
    
    :returns:
    :rtype: 
    """     
    ks_cond = pcr.scalar(TUr > TUw) #caso TUr < TUw, (false, ks = 0)
    # Multiply (TUr - TUw) to avoid negative ln
    Ks = (pcr.ln((TUr - TUw)*ks_cond + 1))/(pcr.ln(TUcc - TUw + 1))
    return Ks

# - Function that returns evapotranspiration of vegetated area
def ETav_calc(self, pcr, ETp, Kc, Ks):
    """
    :param pcr:
    :pcr  type:

    :param ETp:
    :ETp  type:    
    
    :param Kc:
    :Kc  type:

    :param Ks:
    :Ks  type:    
    
    :returns:
    :rtype: 
    """       
    ETav = ETp * Kc * Ks
    return ETav

# - Function that returns Kp for evapotranspiration of open water area
def Kp_calc(self, pcr, B, U_2, UR):
    """
    :param pcr:
    :pcr  type:

    :param B:
    :B  type:    
    
    :param U_2:
    :U_2  type:

    :param UR:
    :UR  type:    
    
    :returns:
    :rtype: 
    """        
    Kp = 0.482+0.024*pcr.ln(B)-0.000376*U_2 + 0.0045*UR
    return Kp

# - Function that returns Ks for evapotranspiration of water area
def ETao_calc(self, pcr, ETp, Kp, prec, Ao):
    """
    :param pcr:
    :pcr  type:

    :param ETp:
    :ETp  type:    
    
    :param Kp:
    :Kp  type:

    :param prec:
    :prec  type:    

    :param Ao:
    :Ao  type:      
    
    :returns:
    :rtype: 
    """           
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)

    ETao_calc = (ETp/Kp)
    
    # conditions for max value for ETao_calc, if ETao_calc > Prec in Pixel with Ao = 1, then ETao = Prec
    cond2 = pcr.scalar((ETao_calc) > prec)
    
    # ET for open water is ET_calc for open water + prec (if ET_calc>prec, for Aio = 1) + ET_calc for Ao = 1, if ET_calc < prec
    ETao = (ETao_calc)*(1-cond1) + prec*cond1*cond2 + (ETao_calc)*cond1*(1-cond2)
    return ETao

# - Function that returns Ks for evapotranspiration of bare soil area
def ETas_calc(self, pcr, ETp, kc_min, Ks):
    """
    :param pcr:
    :pcr  type:

    :param ETp:
    :ETp  type:    
    
    :param kc_min:
    :kc_min  type:

    :param Ks:
    :Ks  type:        
    
    :returns:
    :rtype: 
    """           
    cond = 1*pcr.scalar(Ks != 0) #caso ks seja diferente de 0
    ETas = (ETp*kc_min*Ks*cond)
    return ETas