import bindings
import xmlrpclib
import dicttoxml
import xml.dom.minidom as dom
import socket


#
# Exceptions as defined in the XML-API reference
#

class OneException(Exception):
    pass
class OneAuthenticationException(OneException):
    pass
class OneAuthorizationException(OneException):
    pass
class OneNoExistsException(OneException):
    pass
class OneActionException(OneException):
    pass
class OneApiException(OneException):
    pass
class OneInternalException(OneException):
    pass


##
#
# XML-RPC OpenNebula Server
# Slightly tuned ServerProxy
#
class OneServer(xmlrpclib.ServerProxy):

    #
    # Override the constructor to take the authentication or session
    # Will also configure the socket timeout
    #

    def __init__(self, uri, session, timeout=30, **options):
        self.__session = session
        # note that this will affect other classes using sockets too.
        socket.setdefaulttimeout(timeout)
        xmlrpclib.ServerProxy.__init__(self, uri, **options)

    #
    # Override/patch the (private) request method to:
    # - structured parameters will be casted to attribute=value or XML
    # - automatically prefix all methodnames with "one."
    # - automatically add the authentication info as first parameter
    # - process the response
    def _ServerProxy__request(self, methodname, params):

        # cast parameters, make them one-friendly
        lparams = list(params)
        for i,param in enumerate(lparams):
            lparams[i] = self.__cast(param)
        params = tuple(lparams)

        params = ( self.__session, ) + params
        methodname = "one." + methodname
        try:
            ret = xmlrpclib.ServerProxy._ServerProxy__request(self, methodname, params)
        except xmlrpclib.Fault, e:
            raise OneException(e)

        return self.__response(ret)

    #
    # Process the response from one XML-RPC server
    # will throw exceptions for each error condition
    # will bind returned xml to objects generated from xsd schemas
    def __response(self,rawResponse):
        sucess = rawResponse[0]
        code = rawResponse[2]

        if sucess:
            ret = rawResponse[1]
            if isinstance(ret, basestring):
                # detect xml
                if ret[0] == '<':
                    # dirty-patch the namespace of PyXB won't recognize the type
                    nsXml = "<R xmlns='http://opennebula.org/XMLSchema'>"+ret+"</R>"
                    nsDom = dom.parseString(nsXml)
                    return bindings.CreateFromDOM(nsDom.documentElement.childNodes[0])
            return ret;

        else:
            message = rawResponse[1]
            if code == 0x0100:
                raise OneAuthenticationException(message)
            elif code == 0x0200:
                raise OneAuthorizationException(message)
            elif code == 0x0400:
                raise OneNoExistsException(message)
            elif code == 0x0800:
                raise OneActionException(message)
            elif code == 0x1000:
                raise OneApiException(message)
            elif code == 0x2000:
                raise OneInternalException(message)
            else:
                raise OneException(message)

    #
    # This method will cast parameters to make them nebula friendly
    # flat dictionaries will be turned into attribute=value vectors
    # dictionaries with root dictionary will be serialized as XML
    #
    # Structures will be turned into strings before being submitted.
    def __cast(self,param):

        # if this is a structured type
        if isinstance(param, dict):
            if bool(param):
                root = param.values()[0]
                if isinstance(root, dict):
                    # We return this dictionary as XML
                    return dicttoxml.dicttoxml(param)
                else:
                    # We return this dictionary as attribute=value vector
                    ret = str()
                    for k, v in param.iteritems():
                        ret = ret + k + " = " + str(v) + str('\n')
                    return ret
            else:
                raise OneException("Cannot cast empty dictionary")
        else:
            return param