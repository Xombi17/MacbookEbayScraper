
import asyncio
from app.database.database import init_db, get_db
from rich.console import Console
from rich.table import Table

async def get_status():
    console = Console()
    try:
        await init_db()
        db = get_db()
        
        total = await db.listings.count_documents({})
        notified = await db.listings.count_documents({"is_notified": True})
        rejected = await db.listings.count_documents({"is_rejected": True})
        
        pipeline = [
            {"$match": {"is_rejected": False}},
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$deal_score"},
                "avg_price": {"$avg": "$price"},
                "max_score": {"$max": "$deal_score"}
            }}
        ]
        
        agg_result = await db.listings.aggregate(pipeline).to_list(length=1)
        
        table = Table(title="MacBook Deal Intelligence Status", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="dim")
        table.add_column("Value")
        
        table.add_row("Total Listings", str(total))
        table.add_row("Total Notified", str(notified))
        table.add_row("Total Rejected", str(rejected))
        
        if agg_result:
            stats = agg_result[0]
            table.add_row("Avg Deal Score", f"{stats.get('avg_score', 0):.2f}")
            table.add_row("Avg Price (USD)", f"${stats.get('avg_price', 0):.2f}")
            table.add_row("Top Deal Score", f"{stats.get('max_score', 0):.2f}")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error getting status:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(get_status())
