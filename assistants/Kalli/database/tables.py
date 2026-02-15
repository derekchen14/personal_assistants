"""SQLAlchemy table definitions for Kalli.

Uses portable types (no PostgreSQL-specific dialects) so SQLite works in dev.
"""

import uuid

from sqlalchemy import (
    Column, Integer, String, Text, Float, ForeignKey,
    DateTime, Sequence, JSON, func,
)
from sqlalchemy.orm import declarative_base, relationship, validates

Base = declarative_base()


def _uuid():
    return str(uuid.uuid4())


class Agent(Base):
    __tablename__ = 'agent'

    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True, nullable=False)
    use_case = Column(String, unique=True)


class Conversation(Base):
    __tablename__ = 'conversation'

    id = Column(String(36), primary_key=True, default=_uuid)
    convo_id = Column(Integer, Sequence('convo_id_seq'), unique=True, nullable=False)
    name = Column(Text)
    description = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    status = Column(String(16), default='active')
    source = Column(String(16), default='development')

    agent_id = Column(Integer, ForeignKey('agent.id'), nullable=True)
    username = Column(String(64), nullable=True)

    utterances = relationship('Utterance', back_populates='conversation', cascade='all, delete')


class Utterance(Base):
    __tablename__ = 'utterance'

    id = Column(String(36), primary_key=True, default=_uuid)
    conversation_id = Column(String(36), ForeignKey('conversation.id'))

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    speaker = Column(String(8))
    utt_id = Column(Integer)
    text = Column(Text)
    utt_type = Column(String(32), default='text')
    operations = Column(JSON)
    entity = Column(JSON)
    dact_id = Column(Integer, ForeignKey('dialogue_act.id'))

    conversation = relationship('Conversation', back_populates='utterances')
    dialogue_act = relationship('DialogueAct', back_populates='utterances')

    @validates('speaker')
    def validate_speaker(self, key, speaker):
        assert speaker in ('User', 'Agent'), 'Invalid speaker type'
        return speaker


class Intent(Base):
    __tablename__ = 'intent'

    id = Column(Integer, primary_key=True)
    level = Column(String(8), nullable=False)
    intent_name = Column(String(32), nullable=False)
    description = Column(String)

    dialogue_acts = relationship('DialogueAct', back_populates='intent')


class DialogueAct(Base):
    __tablename__ = 'dialogue_act'

    id = Column(Integer, primary_key=True)
    dact = Column(String(64), nullable=False)
    dax = Column(String(4), nullable=False)
    description = Column(String)
    intent_id = Column(Integer, ForeignKey('intent.id'))
    agent_id = Column(Integer, ForeignKey('agent.id'))

    utterances = relationship('Utterance', back_populates='dialogue_act')
    intent = relationship('Intent', back_populates='dialogue_acts')


class DialogueStateRecord(Base):
    __tablename__ = 'dialogue_state'

    id = Column(String(36), primary_key=True, default=_uuid)
    utterance_id = Column(String(36), ForeignKey('utterance.id'))
    created_at = Column(DateTime, default=func.now())

    intent = Column(String)
    dax = Column(String)
    flow_stack = Column(JSON)
    source = Column(String(8))

    utterance = relationship('Utterance')


class DisplayFrameRecord(Base):
    __tablename__ = 'display_frame'

    id = Column(String(36), primary_key=True, default=_uuid)
    utterance_id = Column(String(36), ForeignKey('utterance.id'))
    created_at = Column(DateTime, default=func.now())

    block_type = Column(String(32))
    content = Column(JSON)
    status = Column(String)

    utterance = relationship('Utterance')


class Lesson(Base):
    __tablename__ = 'lesson'

    id = Column(Integer, Sequence('lesson_id_seq'), primary_key=True)
    content = Column(Text, nullable=False)
    category = Column(String(32))
    tags = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    username = Column(String(64), nullable=True)
