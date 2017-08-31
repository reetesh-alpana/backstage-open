"""

An orchestration framework which follows REST.

License: Apache 2.0 (see LICENSE for details)

__author__ = 'Chandrashekar Jayaraman'
__version__ = '0.1.0-dev'
__license__ = 'APACHE 2.0'

"""

import logging
import os
import re
from urllib import unquote as urlunquote
import core_exceptions

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('backstage')


class Mediator(object):
    def __init__(self):
        self.sequence_list = []

    def mediate(self):
        raise Exception("This needs to be implemented by a subclass")

    def run_internal_sequences(self, context):
        for sequence in self.sequence_list:
            sequence.mediate(context)


class RequestHeader(dict):

    non_http_keys = ('CONTENT_LENGTH', 'CONTENT_TYPE')

    def __init__(self, environ):
        self.environ = environ

    def translate_key(self,key):
        key = key.replace('-','_').upper()
        if key in self.non_http_keys:
            return key
        return 'HTTP_' + key


    def __getitem__(self, key):
        return self.environ[self.translate_key(key)]

    def __setitem__(self, key, value):
        raise TypeError("%s is read-only." % self.__class__)

    def __delitem__(self, key):
        raise TypeError("%s is read-only." % self.__class__)

    def __iter__(self):
        for key in self.environ:
            if key[:5] == 'HTTP_':
                yield key[5:]
            elif key in self.non_http_keys:
                yield key

    def keys_starting_with(self, prefix):
        return [{x[5:]: self.environ[x]} for x in self.environ if x.startswith(self.translate_key(prefix))]

    def keys(self):
        return [x for x in self]

    def raw(self, key, default=''):
        return self.environ.get(key, default)

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return self.translate_key(key) in self.environ


class Request(object):
    def __init__(self, environ):
        self.headers = RequestHeader(environ)
        self.method = self.headers.raw("REQUEST_METHOD")

        if self.method == "GET" or self.method == "DELETE":
            self.query_string = self.headers.raw("QUERY_STRING")
        elif self.method == "POST" or self.method == "PUT" or self.method == 'PATCH':
            self.input = self.headers.raw("wsgi.input")
            self.content_length = int(self.headers.raw("CONTENT_LENGTH"))
            self.body = self.input.read(self.content_length)
            self.query_string = self.headers.raw("QUERY_STRING")

        self.url_path = self.headers.raw("PATH_INFO")
        self.content_type = self.headers.raw("CONTENT_TYPE")

    def __str__(self):
        if self.method == "GET":
            return "Method-%s;Query String - %s;URL -%s" % (self.method, self.query_string, self.url_path)
        elif self.method == "POST" or self.method == "DELETE":
            return "Method-%s;Body-%s;Url-%s;Length-%s" % (
            self.method, self.query_string, self.url_path, self.content_length)

    @property
    def GET(self):
        """
        Return all the query parameters in a dictionary 
        """
        return dict(_parse_qsl(self.query_string))


class Response(object):
    def __init__(self, headers='', body='', status_code='', status_message='', reason=''):
        self.headers = dict()
        self.body = body
        self.status_code = status_code
        self.status_message = status_message
        self.message = body

    def set_headers(self, headers):
        for header, value in headers.iteritems():
            self.headers[header] = value

class Context(object):
    def __init__(self, request, response):
        self.request = request
        self.response = response

    def add_to_context(self, name, key, value):
        registry_value = getattr(self, name)
        value_from_payload = self.get_payload(value)
        registry_value[key] = value_from_payload

    def get_payload(self, payload):
        payload_key, payload_value = payload.split(".")

        if payload_key == "context" and payload_value == "query_string":
            # Convert Query Strings to a dict
            query_parameters = {}
            for query_params in self.request.query_string.split(","):
                key, value = query_params.split("=")
                query_parameters[key] = value
            return query_parameters

        if payload_key == 'context':
            return getattr(self, payload_value)

        message = getattr(self, payload_key)
        if type(message) == type(dict()):
            return message[payload_value]
        else:
            return getattr(message, payload_value)

    def from_request(self, key):
        return getattr(self.request, key, "")

    def from_context(self, key):
        return getattr(self, key, "")


class APIS(object):
    urls_and_apis = {}
    apis = []
    sequences = {}
    
    @classmethod
    def get_url_api(self, request):
        from backstage.conf import settings
        url_path = request.url_path.lstrip("/")
        if settings.APPEND_SLASH and not url_path.endswith("/"):
            url_path += "/"
        api = None
        for url in self.urls_and_apis.keys():
            if re.match(url, url_path):
                api = self.urls_and_apis[url]
        return api

    @classmethod
    def match_url(self, request):
        if self.get_url_api(request):
            return True
        
        raise core_exceptions.Raise404Exception("URI %s not found in defined API's" % request.url_path)

    @classmethod
    def match_method(self, request):
        api = self.get_url_api(request)
        if request.method not in api.supported_methods:
            logger.error("Method %s is not valid for uri %s " %(request.method,
                                                                request.url_path))
            raise core_exceptions.Raise405Exception()
        return api

    @classmethod
    def match_named_sequence(self, sequence_name):
        return APIS.sequences[sequence_name]

    @classmethod
    def sequence_for_uri(self, request, sequence_type):
        """
        Returns the appropriate sequence that matches the URI based on the services.xml
        """
        url_path = request.url_path.lstrip("/")

        # TODO: This method has to be changed once the uri matching is done fine
        api = self.get_url_api(request)
        if api:
            for resource in api.resources:
                if request.method == resource.method:
                    # TODO: Move this to a saner place
                    # Match again with the uri template
                    if hasattr(resource, "uri-template"):
                        combined_url_pattern = "%s%s" % (api.context, getattr(resource, "uri-template"))
                        if re.match(combined_url_pattern, url_path):
                            view_args = re.split(combined_url_pattern, url_path)
                            request.view_args = filter(lambda a: a, view_args)
                        else:
                            continue
                        
                    logger.info(
                        "Sequence returning for %s method, %s url path " % (resource.method, request.url_path))
                    return getattr(resource, ("%s_sequence" % sequence_type))

        # If none of the methods match raise exception
        raise Exception(
            "The sequence type sent '%s' is not supported for the URI '%s' " % (sequence_type, request.url_path))  


class API(object):
    def __init__(self):
        self.resources = []
        self.sequences = {}
        self.name = None
        self.context = None
        self.supported_methods = []
        self.no_of_calls = 0

    def __str__(self):
        return "Name: %s, Context: %s" % (self.name, self.context)


def _parse_qsl(qs):
    r = []
    for pair in qs.replace(';', '&').split('&'):
        if not pair: continue
        nv = pair.split('=', 1)
        if len(nv) != 2: nv.append('')
        key = urlunquote(nv[0].replace('+', ' '))
        value = urlunquote(nv[1].replace('+', ' '))
        r.append((key, value))
    return r


# TODO: Check if this is required and remove from code since we are handling views more
# sanely now
class View(object):
    def __init__(self):
        pass

    def post(self):
        pass

    def get(self):
        pass

    def put(self):
        pass

    def delete(self):
        pass


# TODO: The name is tricky, very similar to NamedSequence
class NamedResource(object):
    def __init__(self):
        self.sequence = []


class Resource(object):
    def __init__(self):
        from mediators import InSequence, OutSequence, FaultSequence

        self.in_sequence = InSequence()
        self.out_sequence = OutSequence()
        self.fault_sequence = FaultSequence()

    def __str__(self):
        return "Method: %s" % (self.method)


# class WSGIHandler(object):
def application(environ, start_response):
    request = Request(environ)

    # Match URI's from APIS because that is where we register everything
    try:
        APIS.match_url(request)
    except core_exceptions.Raise404Exception, e:
        # Send a 404 back to the user
        status = str("404 Not Found")  # HTTP Status
        message = e
        headers = [(str("Content-type"), str("text/plain"))]  # HTTP Headers
        start_response(status, headers)
        return message

    # If requested method is OPTIONS then set the CORS ( Cross origin resource sharing ) responses
    if request.method == 'OPTIONS':
        from backstage.conf import settings
        status = str("200 Ok")
        message = ""
        headers = [
                    (str("Access-Control-Allow-Origin"), str("*")),
                    (str("Access-Control-Allow-Methods"), "DELETE,GET,HEAD,POST,PUT,OPTIONS,PATCH,TRACE"),
                    (str("Access-Control-Allow-Headers"), ','.join(settings.CORS_ALLOWED_HEADERS)),
        ]
        start_response(status, headers)
        return message

    # Match the requested method
    try:
        api = APIS.match_method(request)
    except core_exceptions.Raise405Exception, e:
        # Send a 405 back to the user
        status = str("405 Method Not Supported")  # HTTP Status
        message = e
        headers = [(str("Content-type"), str("text/plain"))]  # HTTP Headers
        start_response(status, headers)
        logger.info("Sending response ")
        return message

    try:
        # Parse the XML element and run this in sequence
        # Initialise a context object with request which can be shared across
        context = Context(request, Response())

        # Add the api object to the context object
        setattr(context, '_api_object', api)

        # Run all the Pre Processors here
        from conf.settings import REQUEST_PROCESSORS
        for processor in REQUEST_PROCESSORS:
            processor().pre_process(request)

        # Run the insequence first
        sequence_to_be_followed = APIS.sequence_for_uri(request, "in")

        for sequence in sequence_to_be_followed.sequence_list:
            logging.info("Sequence being called %s " % sequence.__class__.__name__)
            if hasattr(context, 'break_sequence') and context.break_sequence:
                logging.info("Encountered a break request so breaking off !!")
                break
            else:
                sequence.mediate(context)
    except core_exceptions.RunOutSequence, e:
        # Run the outSequence
        out_sequence_to_be_followed = APIS.sequence_for_uri(context.request, "out")
        # Parse the XML element and run this in sequence
        for sequence in out_sequence_to_be_followed.sequence_list:
            logging.info("Out Sequence being called %s " % sequence.__class__.__name__)
            sequence.mediate(context)
    except Exception, e:
        # Any exception occurs during the process run the fault sequence
        import traceback
        print traceback.format_exc()

        fault_sequence_to_be_followed = APIS.sequence_for_uri(request, "fault")
        for sequence in fault_sequence_to_be_followed.sequence_list:
            sequence.mediate(context)

            # TODO: Return the fault message from here
            # TODO: If the inbuilt exception is an HTTP exception generated from somewhere
            #      that has to be handled separately. Any unknown exception has to be
            #      returned as a 500
    finally:
        # Run all the Post Processors here
        from conf.settings import REQUEST_PROCESSORS
        for processor in REQUEST_PROCESSORS:
            processor().post_process(request)

        if not context.response.status_code:
            raise Exception("No status code set in the response !!")

        status = "%s %s" % (context.response.status_code, context.response.status_message)

        headers = []
        for header_name, header_value in context.response.headers.iteritems():
            headers.append((str(header_name), str(header_value)))

        message = str(context.response.message)

        start_response(status, headers)
        return iter([message])


def parse_services_xml(file_name, api):
    # Read services directory from the settings file
    from conf.settings import HANDLERS
    from mediators import NamedSequences

    from lxml import etree
    apis_tree = etree.parse(file_name)

    # The root of the tree could containg either a sequence or apis, sequence is stored as
    # a dict in the api object

    def create_handler(element):
        Handler = HANDLERS.get(element.tag)
        if not Handler:
            print "%s does not have a proper handler defined " % element.tag
        handler = Handler()
        for item in element.items():
            setattr(handler, item[0], item[1])
        return handler

    def parse_children(element, main_handler):
        for el in element.getchildren():
            handler = create_handler(el)
            main_handler.sequence_list.append(handler)
            parse_children(el, handler)
    if apis_tree.getroot().tag == 'sequence':
        # named_resource = NamedResource()
        sequence_element = apis_tree.getroot()
        sequence_name = sequence_element.get('name')
        sequence_dict = {sequence_name: []}
        sequence_list = []
        for element in sequence_element.getchildren():
            Handler = HANDLERS.get(element.tag)
            if Handler is None:
                raise Exception("Handler for %s is not defined " % element.tag)
            main_handler = Handler()
            for ii in element.items():
                setattr(main_handler, ii[0], ii[1])
            sequence_list.append(main_handler)
            parse_children(element, main_handler)
        sequence_dict[sequence_name] = sequence_list
        # named_resource.sequence = sequence_list
        # api.sequences.update(sequence_dict)
        # APIS.sequences[sequence_name] = sequence_list
        NamedSequences.sequences[sequence_name] = sequence_list

    # tree should contain a list of all the apis
    for single_api in apis_tree.findall("api"):
        api = API()
        for item in single_api.items():
            setattr(api, item[0], item[1])
        APIS.apis.append(api)

        # Each API should have resources
        for internal_resources in single_api.findall("resource"):
            resource = Resource()
            for resource_item in internal_resources.items():
                setattr(resource, resource_item[0], resource_item[1])
            api.resources.append(resource)

            # Add supported methods to the API and not to resource
            api.supported_methods.append(resource.method)

            def create_handler(element):
                Handler = HANDLERS.get(element.tag)
                if not Handler:
                    print "%s does not have a proper handler defined " % element.tag
                handler = Handler()
                for item in element.items():
                    setattr(handler, item[0], item[1])
                return handler

            def parse_children(element, main_handler):
                for el in element.getchildren():
                    handler = create_handler(el)
                    main_handler.sequence_list.append(handler)
                    parse_children(el, handler)

            for element in internal_resources.find("inSequence"):
                Handler = HANDLERS.get(element.tag)
                if Handler is None:
                    raise Exception("Handler for %s is not defined " % element.tag)
                main_handler = Handler()
                for ii in element.items():
                    setattr(main_handler, ii[0], ii[1])
                resource.in_sequence.sequence_list.append(main_handler)
                parse_children(element, main_handler)

            if internal_resources.find("outSequence"):
                # Parse all the OutSequences
                for element in internal_resources.find("outSequence"):
                    Handler = HANDLERS.get(element.tag)
                    if Handler is None:
                        raise Exception("Handler for %s is not defined " % element.tag)
                    handler = Handler()
                    for ii in element.items():
                        setattr(handler, ii[0], ii[1])
                    resource.out_sequence.sequence_list.append(handler)
                    parse_children(element, handler)

            if internal_resources.find("faultSequence"):
                # Parse all the FaultSequences
                for element in internal_resources.find("faultSequence"):
                    Handler = HANDLERS.get(element.tag)
                handler = Handler()
                for ii in element.items():
                    setattr(handler, ii[0], ii[1])
                resource.fault_sequence.sequence_list.append(handler)
                for ll in element.getchildren():
                    Handler = HANDLERS.get(ll.tag)
                    handler = Handler()
                    for ii in ll.items():
                        setattr(handler, ii[0], ii[1])
                    handler.sequence_list.append(handler)

    for api in APIS.apis:
        APIS.urls_and_apis[api.context] = api
        logger.debug("These are the apis %s" % api)
        for resource in api.resources:
            logger.debug("These are the resources %s, %s " % (resource, resource.in_sequence.sequence_list))


#def resource_to_cache():
#    from conf.settings import REDIS_SERVER, REDIS_PORT, RESOURCE_FOLDER, REDIS_DB
#    import redis
#
#    r = redis.StrictRedis(host=REDIS_SERVER, port=REDIS_PORT, db=REDIS_DB)
#    if os.path.isdir(RESOURCE_FOLDER):
#        logger.info("Parsing resource folder")
#        # TODO: Should be able to parse sub folders for resources
#        for filename in os.listdir(RESOURCE_FOLDER):
#            if not filename.endswith(".resource"): continue
#            # Read file content
#            resource_file_full_path = os.path.join(RESOURCE_FOLDER, filename)
#            resource_file = open(resource_file_full_path, 'r')
#            r.set(filename, resource_file.read())
#            logger.info("Setting %s content into cache" % (filename))


#def clear_cache_resources():
#    from conf.settings import REDIS_SERVER, REDIS_PORT, REDIS_DB
#    import redis
#    r = redis.StrictRedis(host=REDIS_SERVER, port=REDIS_PORT, db=REDIS_DB)
#    r.flushdb()
#    logger.info("Cleared redis resources cache %s " % REDIS_DB)


def run():
    import sys
    # Work directory contains all the apps that we would be working with    
    file_names = sys.argv[2]

    for file_name in file_names.split(","):
        sys.path.append(file_name)

    api = API()

    # Check if file_name is a file or a directory. If a directory is passed
    # then all the xml's in the directory have to be parsed.
    for file_name in file_names.split(","):
        if os.path.isdir(file_name):
            # Pick all the xml's in the directory, try and parse them. In case the xml is not
            # a valid backstage xml then we quietly move on.
            logger.info("Parsing directory %s " % file_name)
            for filename in os.listdir(file_name):
                if not filename.endswith('.xml'): continue
                config_file_name = os.path.join(file_name, filename)
                logger.info("Parsing file %s " % filename)
                parse_services_xml(config_file_name, api)
        else:
            logger.info("Parsing services xml %s" % file_name)
            parse_services_xml(file_name, api)

    # Clear resources cache
    #clear_cache_resources()

    # Push all the files in the resource folder to the redis cache
    #resource_to_cache()

