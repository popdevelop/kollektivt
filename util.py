import math

def uniq(seq, idfun=None):
    """
    Return the unique list of dicts.
    Call with uniq(o, idfun=operator.itemgetter("a")) to do it based on an item in
    the dictionary
    """
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result

def atanh(x):
    """arctangent hyperbolicus"""
    return 1.0/2.0*math.log((1.0 + x)/(1.0 -x))

def RT90_to_WGS84(X, Y):
    """
    Input is X and Y coordinates in RT90 as float
    Output is lat and long in degrees, float as tuple
    """
    # Some constants used for conversion to/from Swedish RT90
    f = 1.0/298.257222101
    e2 = f*(2.0-f)
    n = f/(2.0-f)
    L0 = math.radians(15.8062845294)   # 15 deg 48 min 22.624306 sec
    k0 = 1.00000561024
    a = 6378137.0   # meter
    at = a/(1.0+n)*(1.0+ 1.0/4.0* pow(n,2)+1.0/64.0*pow(n,4))
    FN = -667.711 # m
    FE = 1500064.274 # m

    xi = (X - FN)/(k0*at)
    eta = (Y - FE)/(k0*at)
    D1 = 1.0/2.0*n - 2.0/3.0*pow(n,2) + 37.0/96.0*pow(n,3) - 1.0/360.0*pow(n,4)
    D2 = 1.0/48.0*pow(n,2) + 1.0/15.0*pow(n,3) - 437.0/1440.0*pow(n,4)
    D3 = 17.0/480.0*pow(n,3) - 37.0/840.0*pow(n,4)
    D4 = 4397.0/161280.0*pow(n,4)
    xip = xi - D1*math.sin(2.0*xi)*math.cosh(2.0*eta) - \
               D2*math.sin(4.0*xi)*math.cosh(4.0*eta) - \
               D3*math.sin(6.0*xi)*math.cosh(6.0*eta) - \
               D4*math.sin(8.0*xi)*math.cosh(8.0*eta)
    etap = eta - D1*math.cos(2.0*xi)*math.sinh(2.0*eta) - \
                 D2*math.cos(4.0*xi)*math.sinh(4.0*eta) - \
                 D3*math.cos(6.0*xi)*math.sinh(6.0*eta) - \
                 D4*math.cos(8.0*xi)*math.sinh(8.0*eta)
    psi = math.asin(math.sin(xip)/math.cosh(etap))
    DL = math.atan2(math.sinh(etap),math.cos(xip))
    LON = L0 + DL
    A = e2 + pow(e2,2) + pow(e2,3) + pow(e2,4)
    B = -1.0/6.0*(7.0*pow(e2,2) + 17*pow(e2,3) + 30*pow(e2,4))
    C = 1.0/120.0*(224.0*pow(e2,3) + 889.0*pow(e2,4))
    D = 1.0/1260.0*(4279.0*pow(e2,4))
    E = A + B*pow(math.sin(psi),2) + \
            C*pow(math.sin(psi),4) + \
            D*pow(math.sin(psi),6)
    LAT = psi + math.sin(psi)*math.cos(psi)*E
    LAT = math.degrees(LAT)
    LON = math.degrees(LON)
    return LAT, LON

def WGS84_to_RT90(lat, lon):
    """
    Input is lat and lon as two float numbers
    Output is X and Y coordinates in RT90
    as a tuple of float numbers

    The code below converts to/from the Swedish RT90 koordinate
    system. The converion functions use "Gauss Conformal Projection
    (Transverse Marcator)" Kruger Formulas.
    The constanst are for the Swedish RT90-system.
    With other constants the conversion should be useful for
    other geographical areas.

    """
    # Some constants used for conversion to/from Swedish RT90
    f = 1.0/298.257222101
    e2 = f*(2.0-f)
    n = f/(2.0-f)
    L0 = math.radians(15.8062845294)   # 15 deg 48 min 22.624306 sec
    k0 = 1.00000561024
    a = 6378137.0   # meter
    at = a/(1.0+n)*(1.0+ 1.0/4.0* pow(n,2)+1.0/64.0*pow(n,4))
    FN = -667.711 # m
    FE = 1500064.274 # m

    #the conversion
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    A = e2
    B = 1.0/6.0*(5.0*pow(e2,2) - pow(e2,3))
    C = 1.0/120.0*(104.0*pow(e2,3) - 45.0*pow(e2,4))
    D = 1.0/1260.0*(1237.0*pow(e2,4))
    DL = lon_rad - L0
    E = A + B*pow(math.sin(lat_rad),2) + \
            C*pow(math.sin(lat_rad),4) + \
            D*pow(math.sin(lat_rad),6)
    psi = lat_rad - math.sin(lat_rad)*math.cos(lat_rad)*E
    xi = math.atan2(math.tan(psi),math.cos(DL))
    eta = atanh(math.cos(psi)*math.sin(DL))
    B1 = 1.0/2.0*n - 2.0/3.0*pow(n,2) + 5.0/16.0*pow(n,3) + 41.0/180.0*pow(n,4)
    B2 = 13.0/48.0*pow(n,2) - 3.0/5.0*pow(n,3) + 557.0/1440.0*pow(n,4)
    B3 = 61.0/240.0*pow(n,3) - 103.0/140.0*pow(n,4)
    B4 = 49561.0/161280.0*pow(n,4)
    X = xi + B1*math.sin(2.0*xi)*math.cosh(2.0*eta) + \
             B2*math.sin(4.0*xi)*math.cosh(4.0*eta) + \
             B3*math.sin(6.0*xi)*math.cosh(6.0*eta) + \
             B4*math.sin(8.0*xi)*math.cosh(8.0*eta)
    Y = eta + B1*math.cos(2.0*xi)*math.sinh(2.0*eta) + \
              B2*math.cos(4.0*xi)*math.sinh(4.0*eta) + \
              B3*math.cos(6.0*xi)*math.sinh(6.0*eta) + \
              B4*math.cos(8.0*xi)*math.sinh(8.0*eta)
    X = int(X*k0*at + FN)
    Y = int(Y*k0*at + FE)
    return (X, Y)
