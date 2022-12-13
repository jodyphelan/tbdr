from sqlalchemy import MetaData
from sqlalchemy import Table, Column, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import ForeignKey
from sqlalchemy import create_engine


engine = create_engine("postgresql+psycopg2://@localhost/myinner_db", echo=True)
metadata_obj = MetaData()

submission_table = Table(
    "submissions",
    metadata_obj,
    Column("id", String, primary_key=True),
    Column("runs", JSONB)
)

samples_table = Table(
    "samples",
    metadata_obj,
    Column('id', String, primary_key=True),
    Column('public', Boolean),
    Column('country', String),
    Column('date', String),
    Column('drtype', String),
    Column('lineage', String),
    Column('spoligotype', String)
)

results_table = Table(
    "results",
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('status', String),
    Column('data', JSONB),
    Column('sample_id', ForeignKey("samples.id"), nullable=False),
)

variant_table = Table(
    "variants",
    metadata_obj,
    Column('id', String, primary_key=True),
    Column('gene', String),
    Column('locus_tag', String),
    Column('change', String),
    Column('type', String),
    Column('drugs', String)
)

sample_variant_table = Table(
    "sample_variants",
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('sample_id', ForeignKey("samples.id"), nullable=False),
    Column('variant_id', ForeignKey("variants.id"), nullable=False),
    
)

metadata_obj.create_all(engine)