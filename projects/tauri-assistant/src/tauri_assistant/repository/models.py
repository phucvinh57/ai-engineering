from __future__ import annotations

import peewee as pw

database_proxy = pw.DatabaseProxy()


class BaseModel(pw.Model):
    class Meta:
        database = database_proxy


class VariantRecord(BaseModel):
    fingerprint = pw.CharField(primary_key=True)
    config_json = pw.TextField()
    embedding_model = pw.CharField()
    strategy = pw.CharField()
    collection_name = pw.CharField()
    created_at = pw.DoubleField()

    class Meta:
        table_name = "variant"


class IngestRun(BaseModel):
    fingerprint = pw.CharField(index=True)
    started_at = pw.DoubleField()
    finished_at = pw.DoubleField(null=True)
    repo_shas = pw.TextField(null=True)
    docs_total = pw.IntegerField(default=0)
    sources_total = pw.IntegerField(default=0)
    chunks_written = pw.IntegerField(default=0)
    embed_seconds = pw.DoubleField(default=0)
    token_stats = pw.TextField(null=True)
    status = pw.CharField(default="running")

    class Meta:
        table_name = "ingest_run"


class ParentSection(BaseModel):
    fingerprint = pw.CharField()
    parent_id = pw.CharField()
    document_id = pw.CharField()
    text = pw.TextField()

    class Meta:
        table_name = "parent_section"
        primary_key = pw.CompositeKey("fingerprint", "parent_id")
        indexes = ((("fingerprint", "document_id"), False),)


class EvalRun(BaseModel):
    fingerprint = pw.CharField(index=True)
    dataset = pw.CharField()
    created_at = pw.DoubleField()
    metrics_json = pw.TextField()

    class Meta:
        table_name = "eval_run"


MODELS = (VariantRecord, IngestRun, ParentSection, EvalRun)
