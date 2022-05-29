import sys
import datetime
import json
import os
import os.path
import time
import requests

import numpy as np
import pandas as pd
import math




class ApiException(Exception):
    pass

def get_tick(session):
    resp=session.get('http://localhost:9999/v1/case')
    if resp.ok:
        case=resp.json()
        return case['tick']
    
def ticker_bid_ask(s,ticker):
    p={'ticker':ticker,'limit':2}
    resp=s.get('http://localhost:9999/v1/securities/book', params=p)
    if resp.ok:
        book=resp.json()
        return book['bids'][0]['price'], book['asks'][0]['price']
    raise ApiException("Error")

    
    
def square_order(s,ticker,order_type,side,quantity,price,max_qty,inventory,limit_orders):
    print("Inside square_order")
    
    resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': order_type, 'quantity': quantity, 'action': side, 'price': price })
    if order_type=="MARKET":
        if resp.ok:              
            print("The market square "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity) + "qty at" + str(price) )   
        else:            
            print("square_order failed")
    else:
        if resp.ok:
            mkt_order = resp.json()            
            id = mkt_order['order_id']  
            limit_orders[id]=get_tick(s)
            print("The limit square "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity) + "qty at" + str(price) )   
        else:            
            print("square_order failed")

def lose_inventory(s,ticker,qty,inventory_loss):
    print("Inside lose_inventory")
    print(qty)
    if qty>0:
        side="SELL"
    else:
        side="BUY"
    quantity=abs(qty)*inventory_loss
    max_size=10000
    if ticker=="USD":
        max_size=2500000
    while quantity>max_size:
        resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': "MARKET", 'quantity': max_size, 'action': side })
        if resp.ok:              
            print("The lose inventory "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(max_size)  )   
        else:            
            print("lose_inventory failed for innner loop")
        quantity-=max_size
    resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': "MARKET", 'quantity': quantity, 'action': side })
    if resp.ok:              
        print("The lose inventory "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity)  )   
    else:            
        print("lose_inventory failed for last qty")
       
    
    
def place_order(s,ticker,order_type,side,quantity,price,max_qty,inventory,limit_orders,inventory_loss,price_levels):
    print("Inside place_order")
    qty=inventory[ticker]
    if side=="BUY":
        multiplier=-1
        multiplier_stock=1
    else:
        multiplier=1
        multiplier_stock=-1
    if ticker=="USD" and (quantity+inventory[ticker])>=max_qty[ticker] :
        print("Too much invenotry of USD")
        lose_inventory(s,ticker,qty,inventory_loss)
        
    elif ticker=="RITC" and ( abs( inventory['USD'] +  multiplier*price*qty)>= max_qty['USD'] or abs(multiplier_stock*quantity+inventory[ticker]) >= max_qty[ticker] ):
        print("Too much invenotry of RITC")
        lose_inventory(s,ticker,qty,inventory_loss)
    elif abs( inventory['CAD'] +  multiplier*price*qty)>= max_qty['CAD'] or abs(multiplier_stock*quantity+inventory[ticker]) >= max_qty[ticker]:
        print("Too much invenotry of " + str(ticker) )
        lose_inventory(s,ticker,qty,inventory_loss)
        
    else:
        
        
        
        if (price,side) not in price_levels or price_levels[(price,side)]<50000:
            if (price,side) in price_levels:
                quantity=50000 - price_levels[(price,side)]
                
            if order_type=="MARKET":
                resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': order_type, 'quantity': quantity, 'action': side })
                if   resp.ok:            
                    mkt_order = resp.json()            
                    print("Order Id: " + str(mkt_order['order_id']) + " The market "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity) + " qty at " + str(price)  + " at " + str(get_tick(s)) )   
                    if (price,side) in price_levels:
                        
                        price_levels[(price,side)]+=quantity
                    else:
                        price_levels[(price,side)]=quantity     
                else:            
                    print("place_order market failed")
            else:
                resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': order_type, 'quantity': quantity, 'action': side, 'price': price })
                if   resp.ok:            
                    mkt_order = resp.json()            
                    id = mkt_order['order_id']  
                    if (price,side) in price_levels:
                        
                        price_levels[(price,side)]+=quantity
                    else:
                        price_levels[(price,side)]=quantity
                    limit_orders[id]=get_tick(s)
                    print("Order Id: " + str(mkt_order['order_id']) + " The limit "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity) + " qty at " + str(price)  + " at " + str(get_tick(s)) )   
                else:            
                    print("place_order limit failed")
        else:
            print("Order already present in orderbook at the price")

                
                
def etf_arb(s,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask, RITC_bid,RITC_ask, USD_bid,USD_ask,CAD_bid, CAD_ask,quote,max_qty,inventory,limit_orders,inventory_loss,step_size,spread_limit,price_levels):
#     bull=(BULL_bid+BULL_ask)/2
#     bear=(BEAR_bid+BEAR_ask)/2
#     usd=(USD_bid+USD_ask)/2
#     ritc=(RITC_bid+RITC_ask)/2
    
    print("Inside etf_arb")
    diff1 = RITC_ask*USD_bid - (BULL_bid + BEAR_bid)
    diff2 = (BULL_ask + BEAR_ask) - RITC_bid*USD_ask 
    print("diff1,diff2")
    print(diff1,diff2)
    if abs(diff1)>abs(diff2) and diff1>0.2:
        spread=max(0.02,diff1*quote/100)
        ritc_qty=inventory["RITC"]
        #usd_qty=inventory["USD"]
        print("Spread, diff1, diff1*quote")
        print(spread,diff1,diff1*quote/100)
        if spread>=spread_limit[0]:
            print("fd")
            order_type="LIMIT"
            order_size=min(step_size*0.2, qty_level(s,"BULL","BUY"),qty_level(s,"BEAR","BUY"))
#             place_order(s,"BULL",order_type,"BUY",order_size,min(BULL_bid+spread,BULL_ask-0.01),max_qty,inventory,limit_orders,inventory_loss,price_levels)
#             place_order(s,"BEAR",order_type,"BUY",order_size,min(BEAR_bid+spread,BEAR_ask-0.01),max_qty,inventory,limit_orders,inventory_loss,price_levels)
            
#             if (BULL_ask-BULL_bid)>0.08:
            if (BULL_ask+BULL_bid)/2 <9.9:
                place_order(s,"BULL","MARKET","BUY",order_size,BULL_ask,max_qty,inventory,limit_orders,inventory_loss,price_levels)
                place_order(s,"BULL",order_type,"SELL",order_size,BULL_ask+0.1,max_qty,inventory,limit_orders,inventory_loss,price_levels)
#             if (BEAR_ask-BEAR_bid)>0.08:
            if (BEAR_ask+BEAR_bid)/2 <14.9:
                place_order(s,"BEAR","MARKET","BUY",order_size,BEAR_ask,max_qty,inventory,limit_orders,inventory_loss,price_levels)
                place_order(s,"BEAR",order_type,"SELL",order_size,BEAR_ask+0.1,max_qty,inventory,limit_orders,inventory_loss,price_levels)
            
            #cad_quantity=(BULL_bid-spread+BEAR_bid-spread)*order_size
            #place_order(s,"CAD","LIMIT","SELL", cad_quantity,CAD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
            
#             if ritc_qty>0:
#                 place_order(s,"RITC",order_type,"SELL",min(2*order_size,ritc_qty),min(RITC_ask-spread, RITC_bid+0.01),max_qty,inventory,limit_orders,inventory_loss)
#                 usd_qty=min(2*order_size,ritc_qty)*RITC_ask
#                 place_order(s,"USD","LIMIT","BUY",usd_qty,min(USD_bid+spread,USD_ask-0.01),max_qty,inventory,limit_orders,inventory_loss)
                
                #square_order(s,"USD","MARKET","BUY",usd_qty,ritc+spread,max_qty,inventory,limit_orders)
                
            
#             if inventory['USD']< 1*(order_size*(BULL_bid-spread+BEAR_bid-spread)) + order_size*(RITC_ask+spread):
#                 usd_quantity=(order_size*(BULL_bid-spread+BEAR_bid-spread)) + order_size*(RITC_ask+spread)-inventory['USD']
#                 place_order(s,"USD","LIMIT","BUY",usd_quantity,USD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
#             else:
#                 usd_quantity=inventory['USD']- (order_size*(BULL_bid-spread+BEAR_bid-spread)) - order_size*(RITC_ask+spread) 
#                 place_order(s,"USD","LIMIT","SELL",usd_quantity,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
#             if usd_qty>0:
#                 square_order(s,"USD","MARKET","SELL",usd_qty,usd,max_qty,inventory,limit_orders)
#         elif spread>=spread_limit[1]:
#             order_type="LIMIT"
#             order_size=step_size*0.1
#             #price_bull=bull-spread/1.5
#             #price_bear=bear-spread/1.5
#             place_order(s,"BULL",order_type,"BUY",order_size,BULL_bid,max_qty,inventory,limit_orders,inventory_loss)
#             place_order(s,"BEAR",order_type,"BUY",order_size,BEAR_bid,max_qty,inventory,limit_orders,inventory_loss)
#             if ritc_qty>0:
#                 place_order(s,"RITC",order_type,"SELL",min(2*order_size,ritc_qty),RITC_ask,max_qty,inventory,limit_orders,inventory_loss)
#                 usd_qty=min(2*order_size,ritc_qty)*RITC_ask
#                 place_order(s,"USD","LIMIT","BUY",usd_qty,USD_bid+spread,max_qty,inventory,limit_orders,inventory_loss)
#         else:
#             order_type="LIMIT"
#             order_size=step_size*0.05
# #             price_bull=bull-spread/2
# #             price_bear=bear-spread/2
#             place_order(s,"BULL",order_type,"BUY",order_size,BULL_bid,max_qty,inventory,limit_orders,inventory_loss)
#             place_order(s,"BEAR",order_type,"BUY",order_size,BEAR_bid,max_qty,inventory,limit_orders,inventory_loss)
#             if ritc_qty>0:
#                 place_order(s,"RITC",order_type,"SELL",min(2*order_size,ritc_qty),RITC_ask,max_qty,inventory,limit_orders,inventory_loss)
#                 usd_qty=min(2*order_size,ritc_qty)*RITC_ask
#                 place_order(s,"USD","LIMIT","BUY",usd_qty,USD_bid+spread,max_qty,inventory,limit_orders,inventory_loss)
        
            
            
            
    elif diff2>0.2:
        spread=max(0.02,abs(diff2*quote/100))
        #price_ritc=ritc
        #price_usd=usd
        bull_qty=inventory["BULL"]
        bear_qty=inventory["BEAR"]
        print("Spread, diff2, diff2*quote")
        print(spread,diff2,diff2*quote/100)
        if spread>=spread_limit[0]:
            print("fd2")
            order_type="LIMIT"
            order_size=min(step_size*0.2, qty_level(s,"BULL","SELL"),qty_level(s,"BEAR","SELL"))
#             place_order(s,"BULL",order_type,"BUY",order_size,min(BULL_bid+spread,BULL_ask-0.01),max_qty,inventory,limit_orders,inventory_loss,price_levels)
#             place_order(s,"BEAR",order_type,"BUY",order_size,min(BEAR_bid+spread,BEAR_ask-0.01),max_qty,inventory,limit_orders,inventory_loss,price_levels)
            
#             if (BULL_ask-BULL_bid)<-1*0.08:
            if (BULL_ask+BULL_bid)/2 >10.1:
                place_order(s,"BULL","MARKET","SELL",order_size,BULL_bid,max_qty,inventory,limit_orders,inventory_loss,price_levels)
                place_order(s,"BULL",order_type,"BUY",order_size,BULL_bid-0.1,max_qty,inventory,limit_orders,inventory_loss,price_levels)
#             if (BEAR_ask-BEAR_bid)<-1*0.08:
            if (BEAR_ask+BEAR_bid)/2 >15.1:
                place_order(s,"BEAR","MARKET","SELL",order_size,BEAR_bid,max_qty,inventory,limit_orders,inventory_loss,price_levels)
                place_order(s,"BEAR",order_type,"BUY",order_size,BEAR_bid-0.1,max_qty,inventory,limit_orders,inventory_loss,price_levels)
        
        

        
        
        
#         if spread>=spread_limit[1]:
#             order_type="LIMIT"
#             print("fd2")
#             order_size=min(step_size*0.2, qty_level(s,"BULL","SELL"))
# #             place_order(s,"RITC",order_type,"BUY",order_size,min(RITC_bid+spread,RITC_ask-0.01),max_qty,inventory,limit_orders,inventory_loss)
# #             usd_qty=order_size*RITC_bid
# #             place_order(s,"USD","LIMIT","SELL",usd_qty,min(USD_ask-spread,USD_bid+0.01),max_qty,inventory,limit_orders,inventory_loss)
            
#             #place_order(s,"USD","LIMIT","SELL",order_size*(RITC_bid-spread),USD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
#             if bull_qty>0:
# #                 place_order(s,"BULL",order_type,"SELL",min(order_size,bull_qty),min(BULL_ask-spread,BULL_bid+0.01),max_qty,inventory,limit_orders,inventory_loss,price_levels)
                
#                  place_order(s,"BULL",order_type,"SELL",min(order_size,bull_qty),BULL_ask - 0.01,max_qty,inventory,limit_orders,inventory_loss,price_levels)
                
                
                
#                 #place_order(s,"CAD","LIMIT","BUY",bull_qty*(BULL_ask+spread),CAD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
#             if bear_qty>0:   
# #                 place_order(s,"BEAR",order_type,"SELL",min(order_size,bear_qty),min(BEAR_ask-spread,BEAR_bid+0.01),max_qty,inventory,limit_orders,inventory_loss,price_levels)
                
#                 place_order(s,"BEAR",order_type,"SELL",min(order_size,bear_qty),BEAR_ask - 0.01,max_qty,inventory,limit_orders,inventory_loss,price_levels)
                
                
                
                
                #place_order(s,"CAD","LIMIT","BUY",bear_qty*(BEAR_ask+spread),CAD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
            
#             if inventory['USD']< (order_size*(BEAR_ask+spread+BULL_ask+spread)) + order_size*(RITC_bid-spread):
#                 usd_quantity=(order_size*(BEAR_ask+spread+BULL_ask+spread)) + order_size*(RITC_bid-spread)-inventory['USD']
#                 place_order(s,"USD","LIMIT","SELL",usd_quantity,USD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
#             else:
#                 usd_quantity=inventory['USD']- (order_size*(BEAR_ask+spread+BULL_ask+spread)) + order_size*(RITC_bid-spread)
#                 place_order(s,"USD","LIMIT","BUY",usd_quantity,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
            
                #place_order(s,"CAD","MARKET","BUY",order_size,price_bear,max_qty,inventory,limit_orders,inventory_loss)
#         elif spread>=spread_limit[1]:
#             order_type="LIMIT"
#             order_size=step_size*0.1
#             #price_ritc=ritc-spread/1.5
#             place_order(s,"RITC",order_type,"BUY",order_size,RITC_bid,max_qty,inventory,limit_orders,inventory_loss)
#             usd_qty=order_size*RITC_bid
#             place_order(s,"USD","LIMIT","SELL",usd_qty,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
#             if bull_qty>0:
#                 place_order(s,"BULL",order_type,"SELL",min(order_size/2,bull_qty),BULL_ask,max_qty,inventory,limit_orders,inventory_loss)
#             if bear_qty>0:
#                 place_order(s,"BEAR",order_type,"SELL",min(order_size/2,bear_qty),BEAR_ask,max_qty,inventory,limit_orders,inventory_loss)
        
#         else:
#             order_type="LIMIT"
#             order_size=step_size*0.05
#             #price_ritc=ritc-spread/2
#             place_order(s,"RITC",order_type,"BUY",order_size,RITC_bid,max_qty,inventory,limit_orders,inventory_loss)
#             usd_qty=order_size*RITC_bid
#             place_order(s,"USD","LIMIT","SELL",usd_qty,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
#             if bull_qty>0:
#                 place_order(s,"BULL",order_type,"SELL",min(order_size/2,bull_qty),BULL_ask,max_qty,inventory,limit_orders,inventory_loss)
#             if bear_qty>0:
#                 place_order(s,"BEAR",order_type,"SELL",min(order_size/2,bear_qty),BEAR_ask,max_qty,inventory,limit_orders,inventory_loss)
        
        
            
            
def check_limit_orders(s,tick,limit_orders,max_holding_time,inventory):
    #print("Inside check_limit_orders")
    temp=[]
    if len(limit_orders)>=1:
        for order_id in limit_orders:
            #print(order_id)
            link='http://localhost:9999/v1/orders/' + str(order_id)
            resp=s.get(link)
            if  resp.ok:            
                lmt_order = resp.json()    
                if lmt_order['status'] == "OPEN":
                    if (tick-limit_orders[order_id])>max_holding_time:
                        resp_cancel=s.delete(link)
                        if resp_cancel.ok:
                            temp.append(order_id)
                            print("LIMIT order in the market for too long")
                        else:
                            print("Cound not cancel")
                else:
                    temp.append(order_id)
                    print(" ID: "+ str(lmt_order['order_id'])   + " Limit " + str(lmt_order['action']) + " Order filled for " + str(lmt_order['ticker']) + " for " +  str(lmt_order['quantity']) + " at " + str(lmt_order['price']) + " at " +  str(lmt_order['tick']) )
            else:
                print(resp)
                print("Check_limit failed")
    for cancelled in temp:
        del limit_orders[cancelled]

def get_max_limits(s):
    max_qty={}
    print("Max limits")
    resp=s.get('http://localhost:9999/v1/limits')
    if resp.ok:
        limits_json = resp.json()
        for i in limits_json:
            if i['name']=="LIMIT-CASH":
                max_qty['USD']=i['net_limit'] 
                max_qty['CAD']=i['net_limit'] 
            else:
                max_qty['BULL']=i['net_limit'] 
                max_qty['BEAR']=i['net_limit']  
                max_qty['RITC']=i['net_limit']  
    return max_qty
    
    
def get_inventory(s,inventory):
    
    resp = s.get('http://localhost:9999/v1/securities')
    inv = resp.json()
    for i in inv:
        inventory[i["ticker"]]=i["position"]
    
    
def check_currency_pos(s,inventory,max_qty,limit_orders,USD_bid,USD_ask,spread,inventory_loss,currency_spread):
    print("Inside check_currency")
    if inventory['USD']>inventory['CAD']:
        place_order(s,"USD","LIMIT","SELL",inventory['USD']-inventory['CAD'],USD_ask+currency_spread,max_qty,inventory,limit_orders,inventory_loss) 
    else:
        place_order(s,"USD","LIMIT","BUY",inventory['CAD']-inventory['USD'],USD_bid-currency_spread,max_qty,inventory,limit_orders,inventory_loss)
        
       
# def check_tenders(s,tenders,tick,limit_orders,max_holding_time, inventory, max_qty):
#     resp = s.get('http://localhost:9999/v1/tenders')
#     tend = resp.json()
#     for i in tend:
        
    
        
def qty_level(s,ticker,side):
    q=10000
    
    resp=s.get('http://localhost:9999/v1/limits/securities/book', params={'ticker':ticker, 'limit':2})
    if resp.ok:
        book=resp.json()
        if side=="BUY":
            q=book['bids'][0]['quantity']
        else:
            q=book['asks'][0]['quantity']
    return q
        
    
    

def main():     
    with requests.Session() as s: 
        quote=float(sys.argv[1]) ## 10%
        step_size=float(sys.argv[2])  ## 10000
        max_holding_time=float(sys.argv[3])  ## 5
        inventory_loss=float(sys.argv[4]) ## 0.5
        spread_1=float(sys.argv[5]) ## 0.1
        spread_2=float(sys.argv[6]) ## 0.05
        currency_spread=0.005
        spread_limit=[spread_1,spread_2]
        inventory={"BULL" : 0, "BEAR" : 0,"USD" : 0, "RITC" :0, "CAD" :0 }
        API_KEY = {'X-API-key': '8SL0Q95A'} 
        limit_orders={}
        s.headers.update(API_KEY)
        tick=get_tick(s)
        max_qty=get_max_limits(s)
        print(max_qty)
        while tick<=5:
            tick=get_tick(s)
            pass
        tick_arr=[]
        tenders=[]
        price_levels={}
        while tick>3 and tick<=295:
            print("tick is " + str(tick))
            print(inventory)
            BULL_bid, BULL_ask=ticker_bid_ask(s,'BULL')
            BEAR_bid, BEAR_ask=ticker_bid_ask(s,'BEAR')
            RITC_bid, RITC_ask=ticker_bid_ask(s,'RITC')
            USD_bid, USD_ask=ticker_bid_ask(s,'USD')
            CAD_bid, CAD_ask=ticker_bid_ask(s,'CAD')
            print("RITC")
            print(RITC_bid,RITC_ask)
            print("BULL")
            print(BULL_bid,BULL_ask)
            print("BEAR")
            print(BEAR_bid,BEAR_ask)
            print("USD")
            print(USD_bid,USD_ask)


            etf_arb( s,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask, RITC_bid,RITC_ask, USD_bid,USD_ask,CAD_bid, CAD_ask,quote,max_qty,inventory,limit_orders,inventory_loss,step_size,spread_limit,price_levels) 
            get_inventory(s,inventory)
            #check_currency_pos(s,inventory,max_qty,limit_orders,USD_bid,USD_ask,spread,inventory_loss,currency_spread)
            tick_arr.append(tick)
            get_inventory(s,inventory)
            check_limit_orders(s,tick,limit_orders,max_holding_time,inventory)  
            print("------------------------------------------------------------------------------------------------------")
            if tick==295:
                resp=s.post('http://localhost:9999/v1/commands/cancel')
                if resp.ok:
                    print("All limit orders in the book cancelled as stratergy ended")
                else:
                    print("You are fucked")
            tick=get_tick(s)
            
            
if   __name__ == '__main__':     
    main()
   
