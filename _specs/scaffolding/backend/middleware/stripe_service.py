import os
import asyncio
import traceback
from fastapi import HTTPException, Body
import stripe
from fastapi import APIRouter
from dotenv import load_dotenv
from pydantic import BaseModel

# Load Stripe API key from environment variables
load_dotenv()
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
if not STRIPE_API_KEY:
    raise ValueError("STRIPE_API_KEY environment variable is not set")
stripe.api_key = STRIPE_API_KEY

DOMAIN = 'https://www.soleda.ai' if os.getenv('SOLEDA_ENV') == 'production' else 'http://localhost:1414'

# Define price IDs for different plan types
PRICE_IDS = {
    "basic": "price_1RBM2lJ0BU0orn1I0ol6lzL5",  
    "pro": "price_1RBM3GJ0BU0orn1IwTgbq7wf", 
    "enterprise": "price_1RBM4XJ0BU0orn1IgYYOa4WX" 
}

router = APIRouter(prefix="/api/payments", tags=["payments"])
stripe_router = router

# Define request model
class CheckoutRequest(BaseModel):
    planType: str = "basic"

@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutRequest = Body(...)):
    try:
        # Get the plan type from the request
        plan_type = request.planType.lower()
        
        # Get the corresponding price ID or default to basic if not found
        if plan_type not in PRICE_IDS:
            print(f"Invalid plan type: {plan_type}, defaulting to basic")
            plan_type = "basic"
            
        price_id = PRICE_IDS[plan_type]
                
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            return_url=f"{DOMAIN}/static/signup",
            automatic_tax={'enabled': True},
        )
        print("session: ", session)
        return {"client_secret": session.client_secret}
    except stripe.error.StripeError as error:
        raise HTTPException(status_code=400, detail=str(error))