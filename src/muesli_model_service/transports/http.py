from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.runtime.dispatcher import Dispatcher


async def describe_http(dispatcher: Dispatcher):
    request = RequestEnvelope(id="http-describe", op=Operation.DESCRIBE)
    return await dispatcher.dispatch(request)
