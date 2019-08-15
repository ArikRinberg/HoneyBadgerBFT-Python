from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke

import pickle

def _test_honeybadger(N=4, f=1, seed=None):
    sid = 'sidA'
    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)
    with open("sPK.p", "wb") as fh: 
        pickle.dump(sPK, fh)
    with open("sSKs.p", "wb") as fh: 
        pickle.dump(sSKs, fh)
    with open("sPK.p", "rb") as fh: 
        p_sPK = pickle.load(fh)
        print (sPK == p_sPK)
    with open("sSKs.p", "rb") as fh:
        p_sSKs = pickle.load(fh)
        print(p_sSKs == sSKs)
    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)
    with open("ePK.p", "wb") as fh:
        pickle.dump(ePK, fh)
    with open("ePK.p", "rb") as fh:
        p_ePK = pickle.load(fh)
        print(p_ePK == ePK)
    with open("eSKs.p", "wb") as fh:
        pickle.dump(eSKs, fh)
    with open("eSKs.p", "rb") as fh:
        p_eSKs = pickle.load(fh)
        print(eSKs == p_eSKs)
    return

def test_honeybadger():
    _test_honeybadger()


if __name__ == '__main__':
    test_honeybadger()
