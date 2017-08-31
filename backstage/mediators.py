import json
import logging
import re
import urlparse
import uuid
import core_exceptions
from core import Mediator

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('backstage')

class Sequence(Mediator):
    def __init__(self):
        super(Sequence, self).__init__()


class NamedSequences(Sequence):
    sequences = {}

    def __init__(self):
        super(Sequence, self).__init__()


class NamedSequence(Sequence):
    def __init__(self):
        super(NamedSequence, self).__init__()

    def mediate(self, context):
        logger.info("Running named sequence %s" % self.name)
        for sequence in NamedSequences.sequences[self.name]:
            sequence.mediate(context)


class InSequence(Sequence):
    def __init__(self):
        super(InSequence, self).__init__()

    def mediate(self, context):
        logger.info("Inside the InSequence mediator")


class OutSequence(Sequence):
    def __init__(self):
        super(OutSequence, self).__init__()

    def mediate(self, context):
        logger.info("Inside the OutSequence mediator")


class FaultSequence(Sequence):
    def __init__(self):
        super(FaultSequence, self).__init__()

    def mediate(self, context):
        logger.info("Inside the FaultSequence mediator")


class ProcessResponseMediator(Mediator):
    def __init__(self):
        super(ProcessResponseMediator, self).__init__()

    def mediate(self, context):
        # If type is break then there is no need of processing the outsequence
        if hasattr(self, 'type') and self.type == "break":
            setattr(context, 'break_sequence', True)
            return

        # TODO: Rethink this design of raising an exception just because the scope of APIS's is preserved.
        raise core_exceptions.RunOutSequence("Run the Out Sequence !!")


class Property(Mediator):
    def __init__(self):
        super(Property, self).__init__()

    def mediate(self, context):
        """
        This mediator can be used to set information or obtain information from the context, request, response or response header
        The mediator would have 3 properties
        1. action - always 'set' or 'remove'
        2. expression - comma separated list of parameters to be set, the $ symbol along with 
                        context, request or header 
        3. params - comman separated list of values to be set into expression
        
        The expression has to have three parts - $, context/header or request, parameter
        """

        expression_dict = dict(zip(self.expression.split(","), self.params.split(",")))

        for exp, value in expression_dict.iteritems():
            element = None
            backstage_element, parameter = exp.split(".")
            backstage_element = backstage_element.split("$")[1]
            print "This is the backstage element %s " % backstage_element
            if backstage_element == 'context':
                element = context
            elif backstage_element == 'request':
                element = context.request
            elif backstage_element == 'response':
                element = context.response
            elif backstage_element == 'header':
                element = context.response.headers
            else:
                raise Exception("Unknown expression $%s " % backstage_element)

            # If value starts with random id then we generate the random id
            if value.startswith('$random_id'):
                final_value = self.random_id()

            elif value.startswith("$context.") or value.startswith("$request.") or value.startswith(
                    "$response.") or value.startswith("$header"):
                backstage_value, value_parameter = value.split(".")
                # Since the first value is '$'
                backstage_value = backstage_value[1:]
                if backstage_value == 'context':
                    get_element = context
                elif backstage_value == 'response':
                    get_element = context.response
                elif backstage_value == 'header':
                    get_element = context.response.headers

                print "Values being set %s, %s" % (get_element, value_parameter)
                final_value = getattr(get_element, value_parameter, None)
            else:
                final_value = value

            if self.action == 'set' and backstage_element != 'header':
                setattr(element, parameter, final_value)
            elif self.action == 'set' and backstage_element == 'header':
                context.response.headers[parameter] = final_value
                print "Set header value %s ", context.response.headers

    def random_id(self):
        import uuid
        return str(uuid.uuid4())


class Log(Mediator):
    def __init__(self):
        super(Log, self).__init__()

    def mediate(self, context):
        # TODO: Integrate format and handler later.
        log_method = getattr(logger, self.category)
        log_expression = self.value
        if hasattr(self, 'expression'):
            # Check the context variable first and then request
            from_expression = context.from_context(self.expression) or context.from_request(self.expression)
            log_method("%s%s" % (log_expression, from_expression))
        else:
            log_method(log_expression)


class Switch(Mediator):
    run_sequence_first = False

    def __init__(self):
        super(Switch, self).__init__()

    def mediate(self, context):
        logger.info("Inside the switch mediator ")
        context.is_default = True
        if hasattr(self, 'from_header') and self.from_header:
            context.switch_condition = context.from_request(self.from_header)
        elif hasattr(self, 'from_context') and self.from_context:
            context.switch_condition = context.from_context(self.from_context)
        else:
            logger.error("This switch condition cannot be recognized setting default")
        self.run_internal_sequences(context)


class Case(Mediator):
    def __init__(self):
        super(Case, self).__init__()

    def mediate(self, context):
        logger.debug("Inside the Case Mediator ")

        # If there is no switch condition then an error should be thrown
        if not hasattr(context, 'switch_condition'):
            raise Exception("No switch condition ")

        logger.info("This is the switch condition %s " % context.switch_condition)
        if self.value == context.switch_condition:
            self.run_internal_sequences(context)
            context.is_default = False
        else:
            logger.info("Condition does not match here !! ")


class Default(Mediator):
    def __init__(self):
        super(Default, self).__init__()

    def mediate(self, context):
        if hasattr(context, 'is_default'):
            if context.is_default:
                logger.debug("Inside the default mediator ")
                self.run_internal_sequences(context)

class Payload(Mediator):
    def mediate(self, context):
        setattr(context, self.name, dict())
        self.run_internal_sequences(context)


class Use(Mediator):
    def mediate(self, context):
        """
        The use mediator uses values from the context, request or header to set values into 
        a payload object present in the context
        """
        value_to_be_obtained = None

        if self.value.startswith("$context"):
            value_to_be_obtained = getattr(context, self.value.split(".")[1], None)
        elif self.value.startswith("$request"):
            value_to_be_obtained = getattr(context.request, self.value.split(".")[1], None)
        elif self.value.startswith('$header'):
            value_to_be_obtained = context.request.headers.get(self.value.split(".")[1])

        if hasattr(context, self.payload):
            getattr(context, self.payload)[self.key] = value_to_be_obtained
        else:
            setattr(context, self.payload, {self.key: value_to_be_obtained})


class ResponseMediator(Mediator):
    def mediate(self, context):
        if hasattr(self, 'value'):
            context.response.message = self.value
        else:
            # If a direct value is not set it is assumed that the response payload
            # would be set using use_payload
            context.response.message = getattr(context, self.use_payload)

            # If there is an attribute for conversion then find the handler and convert it
            if hasattr(self, 'convert'):
                if not self.convert == 'False':
                    from conf.settings import CONVERTERS
                    context.response.message = CONVERTERS[self.convert]().convert(context.response.message)
        context.response.status_code = self.status_code
        context.response.status_message = self.status_message
        self.run_internal_sequences(context)

class ViewMediator(Mediator):
    def mediate(self, context):
        from conf.settings import VIEW_MEDIATOR_HANDLERS
        actual_view = VIEW_MEDIATOR_HANDLERS[self.handler]
        method = self.method
        view_object = actual_view()
        request_parameters = list()
        request_parameters.append(context.request)
        if hasattr(context.request, 'view_args'):
            request_parameters.extend(context.request.view_args)

        response = getattr(view_object, method)(*request_parameters)

        # Set the respose object into context
        context.response = response

class HttpHeaderMediator(Mediator):
    def mediate(self, context):
        context.response.headers[self.name] = self.value


class PDBMediator(Mediator):
    def mediate(self, context):
        import pdb;
        pdb.set_trace()

