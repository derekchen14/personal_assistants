import os
import json
from typing import Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session
from backend.auth.JWT_helpers import JWTBearer, decode_JWT

from backend.auth.credentials import get_auth_user_email
from backend.db import get_db
from backend.routers.auth_service import get_oauth_credentials
from backend.manager import get_user_id_from_token

external_source_router = APIRouter()

@external_source_router.get('/drive/files/{file_id}')
async def fetch_drive_file(file_id: str, token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  
  try:
    credentials = await get_oauth_credentials(db, user_id, 'drive')
    async with httpx.AsyncClient() as client:
      headers = {
        'Authorization': f'Bearer {credentials.access_token}',
        'Accept': 'application/json'
      }
      url = f"https://sheets.googleapis.com/v4/spreadsheets/{file_id}"
      response = await client.get(url, headers=headers)
      return response.text
    
  except Exception as e:
    print(f"Error fetching drive file: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to fetch file: {str(e)}")

# Get list of files from Google Drive
@external_source_router.get('/drive/files')
async def list_drive_files(token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  
  try:
    credentials = await get_oauth_credentials(db, user_id, 'drive')
    async with httpx.AsyncClient() as client:
      headers = {
        'Authorization': f'Bearer {credentials.access_token}',
        'Accept': 'application/json'
      }
      query = "mimeType='application/vnd.google-apps.spreadsheet'"
      fields = "files(id,name,mimeType,modifiedTime,viewedByMeTime)"
      url = f"https://www.googleapis.com/drive/v3/files?q={query}&fields={fields}"
      
      response = await client.get(url, headers=headers)
      
      if response.status_code != 200:
        print(f"Drive API error: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)
      
      return response.json()

  except Exception as e:
    print(f"Error fetching drive files: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to fetch files: {str(e)}")
  
# Get list of properties from Google Analytics GA4
@external_source_router.get('/ga4/properties')
async def list_ga4_properties(token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  
  try:
    credentials = await get_oauth_credentials(db, user_id, 'ga4')
    async with httpx.AsyncClient() as client:
      headers = {'Authorization': f'Bearer {credentials.access_token}','Accept': 'application/json'}
      url = 'https://analyticsadmin.googleapis.com/v1beta/accountSummaries'
      
      response = await client.get(url, headers=headers)
      
      if response.status_code != 200:
        print(f"GA4 API error: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)
      
      data = response.json()
      properties = []
      
      for account in data.get('accountSummaries', []):
        for prop in account.get('propertySummaries', []):
          properties.append({
            'propertyId': prop.get('property', '').split('/')[-1],  # ID from "properties/123456789"
            'displayName': prop.get('displayName', '')
          })
      
      return {'properties': properties}

  except Exception as e:
    print(f"Error fetching GA4 properties: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to fetch properties: {str(e)}")

async def fetch_child_accounts(client: httpx.AsyncClient, headers: dict, manager_id: str):
  """Helper function to fetch child accounts for a manager account"""
  headers['customer-id'] = manager_id
  url = f"https://googleads.googleapis.com/v18/customers/{manager_id}/googleAds:searchStream"
  
  payload = {
    "query": """
      SELECT 
        customer_client.client_customer,
        customer_client.level,
        customer_client.manager,
        customer_client.descriptive_name,
        customer_client.id
      FROM customer_client
      WHERE customer_client.level = 1
    """
  }
  
  response = await client.post(url, json=payload, headers=headers)
  child_accounts = []
  data = response.json()
  for batch in data:
    for result in batch.get('results', []):
      client_info = result.get('customerClient', {})
      if not client_info.get('manager', False):  # Only include non-manager accounts
        child_accounts.append({
          'id': client_info.get('id'),
          'name': client_info.get('descriptiveName', ''),
          'managerId': manager_id
        })
  return child_accounts

@external_source_router.get('/google/accounts')
async def list_google_accounts(token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  credentials = await get_oauth_credentials(db, user_id, 'google')
  
  async with httpx.AsyncClient() as client:
    headers = {
      'Authorization': f'Bearer {credentials.access_token}', 'Accept': 'application/json',
      'developer-token': os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN'),
    }
    
    # Get manager account list
    customers_url = "https://googleads.googleapis.com/v18/customers:listAccessibleCustomers"
    customers_response = await client.get(customers_url, headers=headers)
    customer_resource_names = customers_response.json().get('resourceNames', [])
    
    all_accounts = []
    manager_accounts = []
    
    # First identify manager accounts
    for resource_name in customer_resource_names:
      customer_id = resource_name.split('/')[-1]
      headers['customer-id'] = customer_id
      
      url = f"https://googleads.googleapis.com/v18/customers/{customer_id}/googleAds:searchStream"
      payload = {
        "query": """
          SELECT 
            customer.id,customer.descriptive_name,customer.manager
          FROM customer
          LIMIT 1
        """
      }
      
      response = await client.post(url, json=payload, headers=headers)
      if response.status_code == 200:
        data = response.json()
        for batch in data:
          for result in batch.get('results', []):
            customer = result.get('customer', {})
            if customer.get('manager', False):
              manager_accounts.append(customer.get('id'))
    
    # Then get child accounts for each manager
    for manager_id in manager_accounts:
      child_accounts = await fetch_child_accounts(client, headers, manager_id)
      all_accounts.extend(child_accounts)
    
    return {'accounts': all_accounts}

@external_source_router.get('/google/campaigns')
async def list_google_campaigns(token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  
  try:
    credentials = await get_oauth_credentials(db, user_id, 'google')
    
    async with httpx.AsyncClient() as client:
      headers = {
        'Authorization': f'Bearer {credentials.access_token}',
        'Accept': 'application/json',
        'developer-token': os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN'),
      }

      # First get all accessible customer IDs
      customers_url = "https://googleads.googleapis.com/v18/customers:listAccessibleCustomers"
      customers_response = await client.get(customers_url, headers=headers)
      customer_resource_names = customers_response.json().get('resourceNames', [])

      # Get manager accounts
      all_campaigns = []
      for resource_name in customer_resource_names:
        customer_id = resource_name.split('/')[-1]
        headers['customer-id'] = customer_id
        
        try:
          # First get account info
          url = f"https://googleads.googleapis.com/v18/customers/{customer_id}/googleAds:searchStream"
          account_query = """
            SELECT 
              customer.id,
              customer.descriptive_name,
              customer.manager
            FROM customer
            LIMIT 1
          """
          
          account_response = await client.post(url, json={"query": account_query}, headers=headers)
          
          if account_response.status_code == 200:
            account_data = account_response.json()
            customer = account_data[0]['results'][0]['customer']
            
            # Skip manager accounts
            if customer.get('manager', False):
              continue
              
            # Get campaigns for this account
            campaign_query = '''
              SELECT 
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type
              FROM campaign
              ORDER BY campaign.name
            '''
            
            campaign_response = await client.post(url, json={"query": campaign_query}, headers=headers)

            if campaign_response.status_code == 200:
              campaign_data = campaign_response.json()
              for batch in campaign_data:
                for result in batch.get('results', []):
                  campaign = result.get('campaign', {})
                  all_campaigns.append({
                    'id': campaign.get('id'),
                    'name': campaign.get('name'),
                    'status': campaign.get('status'),
                    'type': campaign.get('advertisingChannelType'),
                    'accountId': customer.get('id'),
                    'accountName': customer.get('descriptiveName')
                  })
        except Exception as e:
          print(f"Error processing account {customer_id}: {str(e)}")
          continue

      return {'campaigns': all_campaigns}

  except Exception as e:
    print(f"Error fetching Google Ads campaigns: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to fetch campaigns: {str(e)}")

@external_source_router.get('/facebook/campaigns')
async def list_facebook_campaigns(token: str = Depends(JWTBearer()), db=Depends(get_db)):
  user_id = get_user_id_from_token(token)
  
  try:
    credentials = await get_oauth_credentials(db, user_id, 'facebook')
    
    async with httpx.AsyncClient() as client:
      # Get Ad Account ID first
      account_url = "https://graph.facebook.com/v18.0/me/adaccounts"
      headers = {'Authorization': f'Bearer {credentials.access_token}'}
      account_response = await client.get(account_url, headers=headers)
      
      if account_response.status_code != 200:
        raise HTTPException(status_code=account_response.status_code, 
                          detail="Failed to fetch Facebook Ad accounts")
      
      account_data = account_response.json()
      if not account_data.get('data'):
        return {'campaigns': []}
      
      ad_account_id = account_data['data'][0]['id']  # Use first account for now
      # Get campaigns for this account
      campaigns_url = f"https://graph.facebook.com/v18.0/{ad_account_id}/campaigns"
      params = {
        'fields': 'id,name,status,objective,start_time,stop_time'
      }
      
      campaign_response = await client.get(campaigns_url, headers=headers, params=params)
      
      if campaign_response.status_code != 200:
        raise HTTPException(status_code=campaign_response.status_code, 
                          detail="Failed to fetch Facebook campaigns")
        
      campaign_data = campaign_response.json()
      
      return {
        'campaigns': [{
          'id': campaign['id'],
          'name': campaign['name'],
          'status': campaign['status'],
          'objective': campaign.get('objective'),
          'startTime': campaign.get('start_time'),
          'stopTime': campaign.get('stop_time'),
          'accountId': ad_account_id
        } for campaign in campaign_data.get('data', [])]
      }

  except Exception as e:
    print(f"Error fetching Facebook campaigns: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to fetch campaigns: {str(e)}") 