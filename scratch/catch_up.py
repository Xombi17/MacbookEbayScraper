import asyncio
from app.database.database import init_db, get_db
from app.notifications.telegram_notifier import send_deal_alert

async def catch_up():
    await init_db()
    db = get_db()
    
    # Find high-score deals that were never notified
    # We use a simple filter first
    cursor = db.listings.find({
        'deal_score': {'$gte': 7.0},
        'is_notified': {'$ne': True}
    })
    
    missed = await cursor.to_list(length=100)
    print(f'Found {len(missed)} missed high-score deals.')
    
    for listing in missed:
        print(f'Notifying: {listing.get("title")} (Score: {listing.get("deal_score"):.1f})')
        success = await send_deal_alert(listing)
        if success:
            await db.listings.update_one(
                {'_id': listing['_id']},
                {'$set': {'is_notified': True}}
            )
            print(f'  ✓ Marked as notified')
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(catch_up())
