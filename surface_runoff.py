########## Surface runoff ##########

# - Function that returns Ch
def Ch_calc(pcr, self, TUr, dg, Zr, tpor, b):
    tur = TUr/(dg*Zr*10) # [%] soil moisture
    Ch = (tur/tpor)**b
    return Ch

# - Function that returns Cper
def Cper_calc(pcr, self, TUw, dg, Zr, S, manning, w1, w2, w3):
    tuw = TUw/(dg*Zr*10) # [%] soil wilting point
    Cper = w1*(0.02/manning) + w2*(tuw/(1-tuw)) + w3*((S/(10+S)))
    return Cper

# - Function that returns Cimp
def Cimp_calc(pcr, self, ao, ai):
    Aimp = ao + ai
    Cimp = (0.09*pcr.exp((2.4*Aimp)))
    return Aimp, Cimp

# - Function that returns Cwp
def Cwp_calc(pcr, self, Aimp, Cper, Cimp):
    Cwp = (1-Aimp)*Cper+Aimp*Cimp
    return Cwp

# - Function that returns Csr
def Csr_calc(pcr, self, Cwp, P_24, RCD):
    Csr = (Cwp*P_24)/(Cwp*P_24 - RCD*Cwp + RCD)
    return Csr

# - Function that returns Surface runoff
def ES_calc(pcr, self, Csr, Ch, prec, I, Ao, ETao):
    # condition for pixel of water
    cond1 = pcr.scalar(Ao == 1)
    # condition for positive value for (prec - ETao)
    cond2 = pcr.scalar((prec-ETao) >0)
    
    ES = (Csr*Ch*(prec - I))*(1-cond1) + (prec-ETao)*cond2*cond1
    return ES



