import os
import re

with open('mbam_nextgen/services/scheduler_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_method = '''
    async def run_daily_shopping_analysis(self):
        """매일 실행되는 쇼핑 분석 작업 (새벽 5시 일괄 실행)"""
        logger.info(f"[{datetime.now()}] Starting daily scheduled shopping analysis...")
        try:
            from mbam_nextgen.backend.database import SessionLocal, ShoppingTrackedItem, ShoppingHistory
            from mbam_nextgen.backend.routers.shopping_router import fetch_target_rank_via_api, AnalyzeRequest, analyze_keyword_shopping
            
            db = SessionLocal()
            tracked_items = db.query(ShoppingTrackedItem).all()
            if not tracked_items:
                logger.info("No tracked shopping items found.")
                db.close()
                return
                
            for item in tracked_items:
                logger.info(f"Analyzing Shopping Item: {item.name} / Keyword: {item.keyword}")
                try:
                    req = AnalyzeRequest(keyword=item.keyword, target_mid=item.mid)
                    res = await analyze_keyword_shopping(req, db)
                    if res.get('found') and res.get('places'):
                        target_stat = next((p for p in res['places'] if p.get('is_target')), None)
                        if target_stat:
                            date_str = datetime.now().strftime('%Y-%m-%d')
                            # Check if history exists for today
                            existing_hist = db.query(ShoppingHistory).filter(ShoppingHistory.tracked_id == item.id, ShoppingHistory.date_str == date_str).first()
                            if existing_hist:
                                existing_hist.rank = target_stat['rank']
                                existing_hist.page = (target_stat['rank'] - 1) // 40 + 1
                                existing_hist.saves = target_stat['keeps']
                                existing_hist.visitor_reviews = target_stat['reviews']
                                existing_hist.purchases = target_stat['purchases']
                                existing_hist.n1 = target_stat['n1']
                                existing_hist.n2 = target_stat['n2']
                                existing_hist.n3 = target_stat['n3']
                                existing_hist.n4 = target_stat['n4']
                                existing_hist.n5 = target_stat['n5']
                            else:
                                new_hist = ShoppingHistory(
                                    tracked_id=item.id,
                                    date_str=date_str,
                                    rank=target_stat['rank'],
                                    page=(target_stat['rank'] - 1) // 40 + 1,
                                    saves=target_stat['keeps'],
                                    visitor_reviews=target_stat['reviews'],
                                    purchases=target_stat['purchases'],
                                    n1=target_stat['n1'],
                                    n2=target_stat['n2'],
                                    n3=target_stat['n3'],
                                    n4=target_stat['n4'],
                                    n5=target_stat['n5']
                                )
                                db.add(new_hist)
                            db.commit()
                except Exception as e:
                    logger.error(f"Error processing shopping item {item.id}: {str(e)}")
                import asyncio
                await asyncio.sleep(10) # 10초 딜레이
            db.close()
            logger.info("Daily shopping analysis completed.")
        except Exception as e:
            logger.error(f"Failed in daily shopping analysis: {str(e)}")
'''

match = re.search(r'    def _get_scheduled_time\(self\):', content)
if match:
    content = content[:match.start()] + new_method + '\n' + content[match.start():]
    
    # Update start method
    content = content.replace(
        "self.scheduler.add_job(self.run_daily_analysis, 'cron', hour=hour, minute=minute, id='daily_place_analysis', replace_existing=True)",
        "self.scheduler.add_job(self.run_daily_analysis, 'cron', hour=hour, minute=minute, id='daily_place_analysis', replace_existing=True)\n        self.scheduler.add_job(self.run_daily_shopping_analysis, 'cron', hour=hour, minute=minute, id='daily_shopping_analysis', replace_existing=True)"
    )

    with open('mbam_nextgen/services/scheduler_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated scheduler_service.py successfully.')
else:
    print('Failed to find insertion point.')
