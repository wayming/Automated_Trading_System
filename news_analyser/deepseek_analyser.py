import os
import asyncio
import signal
from pathlib import Path
from functools import partial
from common.utils       import new_mq_channel, new_aws_conn
from common.logger      import SingletonLoggerSafe
from news_analyser.providers   import DeepSeekProvider
from news_analyser.executor_proxy import MockTradeExecutorProxy
from news_analyser.trade_policy import TradePolicy
from news_analyser.agent import Agent
from news_analyser.article_analyser import consume_message, graceful_shutdown

# source
QUEUE_TV_ARTICLES = "tv_articles"
# destination
QUEUE_PROCESSED_ARTICLES = "processed_articles"

async def main():
    # Singleton logger
    SingletonLoggerSafe("output/deepseek_analyser.log")

    await SingletonLoggerSafe.ainfo("Connecting to request queue")
    in_queue = None
    out_queue = None
    try:
        channel = await new_mq_channel()
        in_queue = await channel.declare_queue(QUEUE_TV_ARTICLES, durable=True)
        out_queue = await channel.declare_queue(QUEUE_PROCESSED_ARTICLES, durable=True)
    except Exception as e:
        await SingletonLoggerSafe.aerror(f"Failed to connect to RabbitMQ: {e}")
        return

    await SingletonLoggerSafe.ainfo("Creating deepseek analyser")
    provider = DeepSeekProvider()
    analyser = Agent(provider)

    await SingletonLoggerSafe.ainfo("Creating trade executor")
    executor = MockTradeExecutorProxy()
    trade_policy = TradePolicy(executor=executor, logger=SingletonLoggerSafe)

    await SingletonLoggerSafe.ainfo("Optional connecting to AWS Gateway")
    analysis_push_gateway = None
    aws_gateway_endpoint = os.getenv("AWS_GATEWAY_ENDPOINT")
    if not aws_gateway_endpoint:
        await SingletonLoggerSafe.ainfo(" No AWS Gateway endpoint configured. Analysis results will not be pushed.")
    else:
        await SingletonLoggerSafe.ainfo(f" Connecting to AWS Gateway at {aws_gateway_endpoint}")
        try:
            analysis_push_gateway = await new_aws_conn(aws_gateway_endpoint)
        except Exception as e:
            await SingletonLoggerSafe.aerror(f" Failed to initialize gRPC client for AWS Gateway: {e}")
            analysis_push_gateway = None

    await SingletonLoggerSafe.ainfo("Setting up queue consumer")
    await in_queue.consume(
        partial(consume_message,
                analyser=analyser,
                trade_policy=trade_policy,
                analysis_push_gateway=analysis_push_gateway,
                queue_processed_articles=out_queue))

    loop = asyncio.get_running_loop()
    loop_stop = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop_stop.set)

    await SingletonLoggerSafe.ainfo("Consumer started, waiting for messages")
    await loop_stop.wait()
    await graceful_shutdown(channel)


if __name__ == "__main__":
    asyncio.run(main())