from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from tbdr.db import Base

class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(String, primary_key=True)
    runs = Column(JSONB)

class Result(Base):
    __tablename__ = 'results'
    id = Column(Integer, primary_key=True)
    data = Column(JSONB)
    sample_id = Column(String,ForeignKey('samples.id'))
    status = Column(String)


class Sample(Base):
    __tablename__ = 'samples'
    id = Column(String, primary_key=True)
    public = Column('public', Boolean, nullable=False, default=False)
    iso_a3 = Column('iso_a3', String)
    country = Column('country', String)
    year_of_collection = Column('year_of_collection', String)
    drtype = Column('drtype', String)
    lineage = Column('lineage', String)
    spoligotype = Column('spoligotype', String)

class Variant(Base):
    __tablename__ = 'variants'
    id = Column(String, primary_key=True)
    gene = Column(String, nullable=False)
    locus_tag = Column(String, nullable=False)
    type = Column(String, nullable=False)
    change = Column(String, nullable=False)

class SampleVariant(Base):
    __tablename__ = 'sample_variants'
    id = Column(Integer, primary_key=True)
    sample_id = Column(String, ForeignKey('samples.id'), nullable=False)
    variant_id = Column(String, ForeignKey('variants.id'), nullable=False)


