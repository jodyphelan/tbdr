from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from tbdr.db import Base, get_db_session
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import insert

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
    sample_name = Column('sample_name', String)
    public = Column('public', Boolean, nullable=False, default=False)
    iso_a3 = Column('iso_a3', String)
    country = Column('country', String)
    year_of_collection = Column('year_of_collection', Integer)
    drtype = Column('drtype', String, )
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

class Drug(Base):
    __tablename__ = 'drugs'
    id = Column(String, primary_key=True)



class VariantDrugConfidence(Base):
    __tablename__ = 'variant_drug_confidence'
    id = Column(Integer, primary_key=True)
    variant_id = Column(String, ForeignKey('variants.id'), nullable=False)
    drug_id = Column(String, ForeignKey('drugs.id'), nullable=False)
    confidence = Column(String, nullable=False)
    source = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    __table_args__ = (
        UniqueConstraint('variant_id', 'drug_id'),
    )

class SampleCollectionLink(Base):
    __tablename__ = 'sample_collection_link'
    id = Column(Integer, primary_key=True)
    sample_id = Column(String, ForeignKey('samples.id'), nullable=False)
    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('sample_id', 'collection_id'),
    )

class Collection(Base):
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    

def add_sample_to_db(sample_id: str):
    """Add a new Sample entry to the database."""
    result = Result.query.filter(Result.sample_id == sample_id).first()
    sample = Sample.query.filter(Sample.id == sample_id).first()
    if result and sample:
        data = result.data
        db_session = get_db_session()
        # update the sample entry with the provided data
        sample.drtype = data.get('drtype')
        sample.lineage = data.get('sub_lineage')
        sample.spoligotype = data.get('spoligotype')
        db_session.add(sample)
        db_session.commit()


        variant_rows = []
        sample_variant_rows = []
        variant_drugs_rows = []
        drug_rows = []
        for var in data['dr_variants']+data['other_variants']:
            variant_row = {
                'id': f"{var['locus_tag']}:{var['change']}",
                'gene': var['gene_name'],
                'locus_tag': var['gene_id'],
                'type': var['type'],
                'change': var['change'],
            }
            if 'drugs' in var:
                for d in var['drugs']:
                    confidence_row = {
                        'variant_id': variant_row['id'],
                        'drug_id': d['drug'],
                        'confidence': d['confidence'],
                        'source': d['source'],
                        'comment': d['comment'] if d['comment']!="" else None
                    }
                    drug_rows.append({'id': d['drug']})
                    variant_drugs_rows.append(confidence_row)
                        
            elif 'annotation' in var:
                for a in var['annotation']:
                    if a['type'] == 'who_confidence':
                        confidence_row = {
                            'variant_id': variant_row['id'],
                            'drug_id': a['drug'],
                            'confidence': a['confidence'],
                            'source': a['source'],
                            'comment': a['comment'] if a['comment']!="" else None
                        }
                        drug_rows.append({'id': a['drug']})
                        variant_drugs_rows.append(confidence_row)




            variant_rows.append(variant_row)
            sample_variant_rows.append({
                'sample_id': sample_id,
                'variant_id': f"{var['gene_id']}:{var['change']}"
            })

        # Insert variants into the variants table, ignoring duplicates
        stmt = insert(Variant).values(variant_rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=['id'])
        db_session.execute(stmt)

        # Insert sample-variant relationships into the sample_variants table
        db_session.bulk_insert_mappings(SampleVariant, sample_variant_rows)


        stmt = insert(Drug).values(drug_rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=['id'])
        db_session.execute(stmt)

        # Insert variant-drug-confidence relationships into the variant_drug_confidence table, ignoring duplicates
        stmt = insert(VariantDrugConfidence).values(variant_drugs_rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=['variant_id', 'drug_id'])
        db_session.execute(stmt)


        db_session.commit()
