"""
SSL

@copyright: Copyright (c) 2005 Open Source Applications Foundation
@license:   http://osafoundation.org/Chandler_0.1_license_terms.htm
"""

def addCertificates(repView, ctx):
    """
    Add certificates to SSL Context.
    
    @param repView: repository view
    @param ctx: SSL.Context
    """
    #qString = u'for i in "//parcels/osaf/framework/certstore/schema/Certificate" where ((i.type == "root" and i.trust == 3) or (i.type="site" and i.trust == 1))'
    qString = u'for i in "//parcels/osaf/framework/certstore/schema/Certificate" where True'
    
    # XXX Should be done using ref collections instead?
    import repository.query.Query as Query

    qName = 'sslCertificateQuery'
    q = repView.findPath('//Queries/%s' %(qName))
    if q is None:
        p = repView.findPath('//Queries')
        k = repView.findPath('//Schema/Core/Query')
        q = Query.Query(qName, p, k, qString)
        
    store = ctx.get_cert_store()
    for cert in q:
        store.add_x509(cert.asX509())