########## Interception Module ##########

# - Function that returns srmin and srmax
def sr_calc(pcr, self, NDVI):
    SR = (1+NDVI)/(1-NDVI)
    return SR

# - Function that returns Kc
def kc_calc(pcr, self, NDVI, ndvi_min, ndvi_max, kc_min, kc_max):
    Kc = kc_min+((kc_max-kc_min)*((NDVI - pcr.scalar(ndvi_min))/(pcr.scalar(ndvi_max) - pcr.scalar(ndvi_min))))
    return Kc

# - Function that returns fpar
def fpar_calc(pcr, self,fpar_min, fpar_max, SR, sr_min, sr_max):
    fpar_comp = (((SR-sr_min)*(fpar_max-fpar_min)/(sr_max-sr_min))+fpar_min)
    FPAR = pcr.min(fpar_comp, fpar_max)
    return FPAR

# - Function that returns LAI
def lai_function(pcr, self, FPAR, fpar_max, lai_max):
    LAI = lai_max*((pcr.log10(1-FPAR))/(pcr.log10(1-fpar_max)))
    return LAI
   
# - Function that returns Interception
def Interception_function(pcr, self, alfa, LAI, precipitation, rainy_days, a_v):
    # condition of precipitation, to divide by non zero number (missing value)
    cond1 = pcr.scalar((precipitation != 0))
    cond2 = pcr.scalar((precipitation == 0))
    prec = precipitation*cond1 + (precipitation*cond2+0.00001)
 
    Id = alfa*LAI*(1-(1/(1+(precipitation*((1-(pcr.exp(-0.463*LAI)))/(alfa*LAI))))))
    Ir = 1 - pcr.exp(-Id*rainy_days/prec)
    # Interception of the vegetated area
    Iv = precipitation*Ir
    # Total interception
    I = a_v*Iv
    return Id, Ir, Iv, I