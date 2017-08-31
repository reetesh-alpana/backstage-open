from backstage import mediators

REQUEST_PROCESSORS = []

HANDLERS = {
    'inSequence': mediators.InSequence,
    'outSequence': mediators.OutSequence,
    'faultSequence': mediators.FaultSequence,
    'property': mediators.Property,
    'log': mediators.Log,
    'switch': mediators.Switch,
    'case': mediators.Case,
    'default': mediators.Default,
    "processresponse": mediators.ProcessResponseMediator,
    "payload": mediators.Payload,
    "use": mediators.Use,
    "response": mediators.ResponseMediator,
    "header": mediators.HttpHeaderMediator,
    "pdb": mediators.PDBMediator,
    "view": mediators.ViewMediator,
    "sequence": mediators.NamedSequence,
}

APPEND_SLASH = True
