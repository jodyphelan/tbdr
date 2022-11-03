from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from tbdr.db import Base

class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(String, primary_key=True)
    runs = Column(JSONB)

    def __init__(self, id, runs):
        self.id = id
        self.runs = runs

    def __repr__(self):
        return f'<Result {self.id!r}>'    

class Result(Base):
    __tablename__ = 'results'
    id = Column(Integer, primary_key=True)
    data = Column(JSONB)
    sample_id = Column(String,ForeignKey('samples.id'))
    status = Column(String)

    def __init__(self, sample_id, status="queued"):
        self.sample_id = sample_id
        self.status = status

    def __repr__(self):
        return f'<Result {self.sample_id!r}>'

class Sample(Base):
    __tablename__ = 'samples'
    id = Column(String, primary_key=True)

    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return f'<Result {self.id!r}>'

class Variant(Base):
    __tablename__ = 'variants'
    id = Column(String, primary_key=True)
    gene = Column(String, nullable=False)
    change = Column(String, nullable=False)

    def __init__(self, id, gene, change):
        self.id = id
        self.gene = gene
        self.change = change

    def __repr__(self):
        return f'<Variant {self.id!r}>'

class SampleVariant(Base):
    __tablename__ = 'sample_variants'
    id = Column(Integer, primary_key=True)
    sample_id = Column(String, nullable=False)
    variant_id = Column(String, nullable=False)

    def __init__(self, id, sample_id, variant_id):
        self.id = id
        self.sample_id = ForeignKey("samples.id")
        self.variant_id = ForeignKey("variants.id")

    def __repr__(self):
        return f'<SampleVariant {self.id!r}>'
