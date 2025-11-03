# telemetry.py
import os
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Configure a global tracer provider
provider = TracerProvider()
trace.set_tracer_provider(provider)

# Add a Console exporter (prints spans to stdout)
exporter = ConsoleSpanExporter()
span_processor = SimpleSpanProcessor(exporter)

class EnvAttributeProcessor(SpanProcessor):
    def on_start(self, span, parent_context):
        # automatically add environment info when a span starts
        for key in [ 
            "CI_PIPELINE_ID",
            "CI_JOB_NAME",
            "GIT_BRANCH",
            "GIT_COMMIT",
            "RUNNER_NAME",
            "BUILD_ID",
        ]:
            if value := os.getenv(key):
                span.set_attribute(f"env.{key.lower()}", value)

    def on_end(self, span):
        pass

class ConfAttributeProcessor(SpanProcessor):
    def __init__(self, cfg,  instance_id=None):
        self.cfg = cfg
        self.uuid = instance_id
    
    def on_start(self, span, parent_context):
        if self.uuid != None:
            span.set_attribute("Instance Id",self.uuid)
            
        # automatically add configuration info when a span starts
        for key in self.cfg:
            if key == "signing": 
                continue
            else:
                span.set_attribute(f"cfg.{key.lower()}",str(self.cfg[key]))


provider.add_span_processor(EnvAttributeProcessor()) 
provider.add_span_processor(span_processor)

def add_config_attributes(cfg, instance_id):
    provider.add_span_processor(ConfAttributeProcessor(cfg, instance_id)) 


def get_tracer(name: str):
    """Return a tracer for use in other modules."""
    return trace.get_tracer(name)
