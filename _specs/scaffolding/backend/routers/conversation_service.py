from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.orm import Session
from typing import List, Dict
from database.tables import Conversation, ConversationDataSource, UserDataSource, Utterance, DialogueState, Frame
from backend.db import get_db
from backend.auth.JWT_helpers import get_current_user
import pandas as pd
from backend.manager import get_agent_with_token
from backend.auth.JWT_helpers import decode_JWT

conversation_router = APIRouter()

@conversation_router.get("/conversations")
async def get_user_conversations(db: Session = Depends(get_db)) -> List[Dict]:
    return []

"""
async def get_user_conversations(
    auth_token: str = Cookie(None),
    db: Session = Depends(get_db)
) -> List[Dict]:
    Get all conversations for a user with their associated data sources
    try:
        payload = decode_JWT(auth_token)
        user_id = payload.get('userID')
        # Get all conversations for the user
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).all()

        result = []
        for conv in conversations:
            # Get data sources for this conversation
            data_sources = db.query(ConversationDataSource).filter(
                ConversationDataSource.conversation_id == conv.id
            ).all()

            if data_sources:  # Only include conversations with data sources
                source_names = []
                for ds in data_sources:
                    source = db.query(UserDataSource).filter(
                        UserDataSource.id == ds.data_source_id
                    ).first()
                    if source:
                        source_names.append(source.name)

                result.append({
                    "id": str(conv.id),
                    "name": conv.name or "Untitled Conversation",
                    "data_sources": source_names,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None
                })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""

@conversation_router.get("/conversation/{conversation_id}")
async def get_conversation_data(
    conversation_id: str,
    auth_token: str = Cookie(None),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get data for a specific conversation including its data sources, utterances and load them into memory
    """
    try:
        payload = decode_JWT(auth_token)
        user_id = payload.get('userID')
        # Get the conversation
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get data sources for this conversation
        data_sources = db.query(ConversationDataSource).filter(
            ConversationDataSource.conversation_id == conversation.id
        ).all()

        if not data_sources:
            raise HTTPException(status_code=404, detail="No data sources found for this conversation")

        # Get all utterances for this conversation, sorted by created_at
        utterances = db.query(Utterance).filter(
            Utterance.conversation_id == conversation_id
        ).order_by(Utterance.created_at).all()

        # Format utterances
        formatted_utterances = []
        for utt in utterances:
            formatted_utterances.append({
                "id": str(utt.id),
                "role": utt.speaker.lower(),
                "content": utt.text,
                "timestamp": utt.created_at.isoformat() if utt.created_at else None,
                "type": utt.utt_type,
                "operations": utt.operations if utt.operations else []
            })

        # Get the actual data source details and load them into memory
        sources = []
        for ds in data_sources:
            source = db.query(UserDataSource).filter(
                UserDataSource.id == ds.data_source_id
            ).first()
            if source:
                # Load the data source into memory using the agent
                data_analyst = get_agent_with_token(auth_token)
                data_analyst.conversation_id = conversation_id
                data_analyst.data_source_ids = [ds.data_source_id for ds in data_sources]
                table_dict = {}
                table_dict[source.name] = pd.DataFrame({
                    col: data for col, data in zip(source.content['columns'], source.content['data'])
                })

                properties = data_analyst.memory.register_new_data(
                    ss_name=source.name,
                    ss_goal=f'Loaded from {source.provider}',
                    ss_data=table_dict
                )

                preview_frame = data_analyst.register_data_with_agent(properties)
                table_data = preview_frame.get_data('list')

                sources.append({
                    "id": str(source.id),
                    "name": source.name,
                    "provider": source.provider,
                    "content": table_data,
                    "properties": properties
                })

        return {
            "id": str(conversation.id),
            "name": conversation.name or "Untitled Conversation",
            "data_sources": sources,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "utterances": formatted_utterances
        }

    except HTTPException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    auth_token: str = Cookie(None),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Delete a conversation and all its associated data (utterances, dialogue states, frames)
    """
    try:
        payload = decode_JWT(auth_token)
        user_id = payload.get('userID')
        # Get the conversation and verify ownership
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get all utterances for this conversation
        utterances = db.query(Utterance).filter(
            Utterance.conversation_id == conversation_id
        ).all()

        # Delete dialogue states and frames first
        for utterance in utterances:
            # Delete dialogue states
            db.query(DialogueState).filter(
                DialogueState.utterance_id == utterance.id
            ).delete()
            
            # Delete frames
            db.query(Frame).filter(
                Frame.utterance_id == utterance.id
            ).delete()

        # Delete the conversation (cascade will handle utterances and other related records)
        db.delete(conversation)
        db.commit()

        return {"message": "Conversation deleted successfully"}

    except Exception as e:
        import traceback
        print(f"Error deleting conversation: {e}")
        print(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))