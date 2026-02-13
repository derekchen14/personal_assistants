import uuid
import bcrypt
from sqlalchemy import (Column, Integer, String, Text, text, Float, Enum,
                        ForeignKey, DateTime, JSON, Unicode, ARRAY, UUID, func, Sequence)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, validates
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class User(Base):
  __tablename__ = 'user'

  id = Column('id', Integer, Sequence('user_id_seq'), primary_key=True)
  first = Column('first', String, nullable=False)
  middle = Column('middle', String)
  last = Column('last', String)
  email = Column('email', Unicode(128), unique=True, nullable=False)
  password = Column('_password', String(60), nullable=False)
  username = Column('username', String(32), unique=True)

  def __repr__(self):
    return f'<User {self.first} {self.last} ({self.id})>'

  def set_password(self, password):
    encoded = password.encode('utf-8')
    salt = bcrypt.gensalt()
    self.password = bcrypt.hashpw(encoded, salt).decode('utf-8')

  def check_password(self, password):
    password_to_check = password.encode('utf-8')
    stored_password = self.password.encode('utf-8')
    return bcrypt.checkpw(password_to_check, stored_password)

class Agent(Base):
  __tablename__ = 'agent'

  id = Column('id', Integer, primary_key=True)
  name = Column('name', String(32), unique=True, nullable=False)
  use_case = Column('use_case', String, unique=True)

  def __repr__(self):
    return f'<Agent {self.name} ({self.id})>'

class Structure(Base):
  __tablename__ = 'structure'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

  created_at = Column('created_at', DateTime, default=func.now())
  updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
  sequence = Column('sequence', Text)
  content = Column('content', ARRAY(String))
  conversations = relationship("Conversation", back_populates="structure")

  def __repr__(self):
    return f'Structure table: id - <{self.id}>, sequence - <{self.sequence}>, content - <{self.content}>'

class Scenario(Base):
  __tablename__ = 'scenario'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

  created_at = Column('created_at', DateTime, default=func.now())
  updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
  scenario = Column('scenario', Text)
  candidates = Column('candidates', JSON)

  # One-to-many relationship
  conversations = relationship("Conversation", back_populates="scenario")

class Conversation(Base):
  __tablename__ = 'conversation'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  convo_id = Column(Integer, Sequence('convo_id_seq'), unique=True, nullable=False)
  name = Column('name', Text)
  description = Column('description', Text)

  short_embed = Column('short_embed', Vector(384))
  medium_embed = Column('medium_embed', Vector(768))
  long_embed = Column('long_embed', Vector(1536))

  created_at = Column('created_at', DateTime, default=func.now())
  updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
  status = Column('status', Enum('for_review', 'edited', 'skipped', 'completed', name='status_enum'))
  source = Column('source', Enum('synthetic', 'development', 'production', name='source_enum'))

  structure_id = Column('structure_id', UUID(as_uuid=True), ForeignKey('structure.id'), nullable=True)
  scenario_id = Column('scenario_id', UUID(as_uuid=True), ForeignKey('scenario.id'), nullable=True)

  agent_id = Column('agent_id', Integer, ForeignKey('agent.id'), nullable=True)
  user_id = Column('user_id', Integer, ForeignKey('user.id'), nullable=True)

  # Many-to-one relationship
  structure = relationship("Structure", back_populates="conversations")
  scenario = relationship("Scenario", back_populates="conversations")

  # One-to-many relationship
  utterances = relationship("Utterance", back_populates="conversation", cascade="all, delete")
  data_sources = relationship("ConversationDataSource", back_populates="conversation", cascade="all, delete")

  # One-to-one relationship
  comment = relationship("Comment", back_populates="conversation", cascade="all, delete")
  score = relationship("Score", back_populates="conversation", cascade="all, delete")

  def __repr__(self):
    return f'Conversation table: id - <{self.id}>, convo_id - <{self.convo_id}>, status - <{self.status}>, source - <{self.source}>, structure_id - <{self.structure_id}>'

class Utterance(Base):
  __tablename__ = 'utterance'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  conversation_id = Column('conversation_id', UUID(as_uuid=True), ForeignKey('conversation.id'))

  created_at = Column('created_at', DateTime, default=func.now())
  updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
  speaker = Column("speaker", Enum('User', 'Agent', name='speaker'))
  utt_id = Column('utt_id', Integer)
  text = Column('text', Text)
  utt_type = Column('utt_type', String(32), default='text')
  operations = Column('operations', ARRAY(String))
  entity = Column('entity', JSON)
  dact_id = Column('dact_id', Integer, ForeignKey('dialogue_act.id'))

  # Many-to-one relationship
  conversation = relationship("Conversation", back_populates="utterances")
  dialogue_act = relationship("DialogueAct", back_populates="utterances")

  # One-to-one relationship
  # label = relationship("Label", back_populates="turn", cascade="all, delete")

  @validates('speaker')
  def validate_speaker(self, key, speaker):
    assert speaker in ['User', 'Agent', 'System'], 'Invalid speaker type'
    return speaker

  @validates('utt_type')
  def validate_utt_type(self, key, utt_type):
    valid_types = ['text', 'speech', 'multiple_choice', 'image', 'action']
    assert utt_type in valid_types, 'Invalid utterance type'
    return utt_type

  def __repr__(self):
    return f'Turn table: id - <{self.id}>, conversation_id - <{self.conversation_id}>, speaker - <{self.speaker}>, utt_id - <{self.utt_id}>, text - <{self.text}>'

class Intent(Base):
  __tablename__ = 'intent'

  id = Column('id', Integer, primary_key=True)
  level = Column('level', String(8), nullable=False)
  intent_name = Column('intent_name', String(32), nullable=False)
  description = Column('description', String)

  # One-to-many relationship
  dialogue_acts = relationship("DialogueAct", back_populates="intent")

  def __repr__(self):
    return f'<{self.intent_name} ({self.intent_id})>'

class DialogueAct(Base):
  __tablename__ = 'dialogue_act'

  id = Column('id', Integer, primary_key=True)
  dact = Column('dact', String(64), nullable=False)
  dax = Column('dax', String(4), nullable=False)
  description = Column('description', String)
  intent_id = Column('intent_id', Integer, ForeignKey('intent.id'))
  agent_id = Column('agent_id', Integer, ForeignKey('agent.id'))

  # One-to-many relationship
  utterances = relationship("Utterance", back_populates="dialogue_act")

  # many-to-one relationship
  intent = relationship("Intent", back_populates="dialogue_acts")

  def __repr__(self):
    return f'<{self.dact} ({self.dact_id})>'

class DialogueState(Base):
  __tablename__ = 'dialogue_state'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  utterance_id = Column('utterance_id', UUID(as_uuid=True), ForeignKey('utterance.id'))
  created_at = Column('created_at', DateTime, default=func.now())
  
  intent = Column('intent', String)
  dax = Column('dax', String)
  flow_stack = Column('flow_stack', JSONB)

  source = Column('source', Enum('nlu', 'pex', name='dialogue_state_source_enum'))

  # Relationship
  utterance = relationship("Utterance")

  def __repr__(self):
    return f'DialogueState: id - <{self.id}>, utterance_id - <{self.utterance_id}>, intent - <{self.intent}>, dax - <{self.dax}>'

class Frame(Base):
  __tablename__ = 'frame'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  utterance_id = Column('utterance_id', UUID(as_uuid=True), ForeignKey('utterance.id'))
  created_at = Column('created_at', DateTime, default=func.now())
  
  type = Column('type', Enum('direct', 'derived', 'dynamic', 'decision', name='frame_type_enum'))
  columns = Column('columns', ARRAY(String))
  status = Column('status', String)
  source = Column('source', Enum('sql', 'pandas', 'plotly', 'interaction', 'default', name='frame_source_enum'))
  code = Column('code', Text)

  # Relationship
  utterance = relationship("Utterance")

  def __repr__(self):
    return f'Frame: id - <{self.id}>, utterance_id - <{self.utterance_id}>, type - <{self.type}>, source - <{self.source}>'

# class Label(Base):
#   __tablename__ = 'label'
#
#   id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#   turn_id = Column('turn_id', UUID(as_uuid=True), ForeignKey('turn.id'))
#
#   created_at = Column('created_at', DateTime, default=func.now())
#   updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
#   intent = Column('intent', Text)
#   dact = Column('dact', Text)
#   dax = Column('dax', Text)
#   operations = Column('operations', ARRAY(String))
#   entity = Column('entity', Text)
#
#   # One-to-one relationship
#   turn = relationship("Turn", back_populates="label")
#
#   def __repr__(self):
#     return f'Label table: id - <{self.id}>, turn_id - <{self.turn_id}>, intent - <{self.intent}>, dact - <{self.dact}>, dax - <{self.dax}>, operation - <{self.operation}>, entity - <{self.entity}>,'

class Comment(Base):
  __tablename__ = 'comment'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  conversation_id = Column('conversation_id', UUID(as_uuid=True), ForeignKey('conversation.id'))

  created_at = Column('created_at', DateTime, default=func.now())
  updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
  content = Column('content', Text)

  # One-to-one relationship
  conversation = relationship("Conversation", back_populates="comment")

  def __repr__(self):
    return f'Comment table: id - <{self.id}>, conversation_id - <{self.conversation_id}>, content - <{self.content}>'

class Score(Base):
  __tablename__ = 'score'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  conversation_id = Column('conversation_id', UUID(as_uuid=True), ForeignKey('conversation.id'))

  created_at = Column('created_at', DateTime, default=func.now())
  updated_at = Column('updated_at', DateTime, default=func.now(), onupdate=func.now())
  quality = Column('quality', Float)
  accuracy = Column('accuracy', Float)
  total = Column('total', Float)


  # One-to-one relationship
  conversation = relationship("Conversation", back_populates="score")

  def __repr__(self):
    return f'Score table: id - <{self.id}>, quality - <{self.quality}>, accuracy - <{self.accuracy}>, total - <{self.total}>'

class Credential(Base):
  __tablename__ = 'credential'

  id = Column(Integer, primary_key=True, nullable=False, index=True)
  user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
  access_token = Column(String, unique=True, index=True, nullable=False)
  refresh_token = Column(String, unique=False, nullable=True)
  token_expiry = Column(DateTime, nullable=False)
  vendor = Column(String, nullable=False)
  vendor_id = Column(String, nullable=False)
  scope = Column(String)
  last_sync_time = Column(DateTime)
  status = Column(String, nullable=False)
  instance_url = Column(String, unique=False, nullable=True) 
  

class UserDataSource(Base):
  __tablename__ = 'user_data_source'

  id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('uuid_generate_v4()'))
  created_at = Column('created_at', DateTime, server_default=text('CURRENT_TIMESTAMP'))
  updated_at = Column('updated_at', DateTime, server_default=text('CURRENT_TIMESTAMP'))
  user_id = Column(Integer, ForeignKey('user.id'), nullable=False, index=True)
  source_type = Column(Enum('upload', 'api', name='source_type_enum'))
  provider = Column(String)  # 'facebook_ads', 'google_ads', 'csv', 'excel' etc
  name = Column(String, nullable=False)
  size_kb = Column(Integer)
  content = Column(JSONB)

  def __repr__(self):
    return f'User data source table: id - <{self.id}>, user_id - <{self.user_id}>, name - <{self.name}>'

class ConversationDataSource(Base):
  __tablename__ = 'conversation_data_source'

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversation.id', ondelete='CASCADE'), index=True)
  data_source_id = Column(UUID(as_uuid=True), ForeignKey('user_data_source.id', ondelete='CASCADE'), index=True)
  created_at = Column(DateTime, default=func.now())
  updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
  
  # Relationships
  conversation = relationship("Conversation", back_populates="data_sources")
  data_source = relationship("UserDataSource", cascade="all, delete")

  def __repr__(self):
    return f'ConversationDataSource: conversation_id - <{self.conversation_id}>, data_source_id - <{self.data_source_id}>'
