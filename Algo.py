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
    p={'ticker':ticker}
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
            if side=="BUY":
                inventory[ticker]+=quantity
            else:
                inventory[ticker]-=quantity
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
    if qty>0:
        side="SELL"
    else:
        side="BUY"
    quantity=qty*inventory_loss
    resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': "MARKET", 'quantity': quantity, 'action': side })

    if resp.ok:              
        if side=="BUY":
            inventory[ticker]+=quantity
        else:
            inventory[ticker]-=quantity
        print("The lose inventory "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity)  )   
    else:            
        print("lose_inventory failed")
    
    
def place_order(s,ticker,order_type,side,quantity,price,max_qty,inventory,limit_orders,inventory_loss):
    print("Inside place_order")
    qty=inventory[ticker]
    if ticker!="USD" and (qty>=max_qty or qty<=-1*max_qty):
        print("Too much invenotry")
        lose_inventory(s,ticker,qty,inventory_loss)
    if ticker=="USD" and (qty>=max_qty*1 or qty<=-1*max_qty*1):
        print("Too many USD")
        lose_inventory(s,ticker,qty,inventory_loss)
    else:
        if ticker=="USD":
            quantity=quantity*1
        if order_type=="MARKET":
            resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': order_type, 'quantity': quantity, 'action': side })
            if   resp.ok:            
                mkt_order = resp.json()            
                id = mkt_order['order_id']   
                if side=="BUY":
                    inventory[ticker]+=quantity
                else:
                    inventory[ticker]-=quantity
                print("The market "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity) + "qty at" + str(price) )   
            else:            
                print("place_order failed")
        else:
            resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': order_type, 'quantity': quantity, 'action': side, 'price': price })
            if   resp.ok:            
                mkt_order = resp.json()            
                id = mkt_order['order_id']  
                limit_orders[id]=get_tick(s)
                print("The limit "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity) + "qty at" + str(price) )   
            else:            
                print("place_order failed")

                
                
def etf_arb(s,bull,bear,ritc,usd,quote,max_qty,inventory,limit_orders,inventory_loss,step_size,spread_limit):
    print("Inside etf_arb")
    diff = ritc*usd - (bull + bear)
    if diff>0.02:
        spread=max(0.02,diff*quote/100)
        price_bull=bull
        price_bear=bear
        ritc_qty=inventory["RITC"]
        usd_qty=inventory["USD"]
        if spread>=spread_limit[0]:
            order_type="MARKET"
            order_size=step_size*0.4
            place_order(s,"BULL",order_type,"BUY",order_size,price_bull,max_qty,inventory,limit_orders,inventory_loss)
            place_order(s,"BEAR",order_type,"BUY",order_size,price_bear,max_qty,inventory,limit_orders,inventory_loss)
            if ritc_qty>0:
                square_order(s,"RITC","MARKET","SELL",ritc_qty,ritc+spread,max_qty,inventory,limit_orders)
#             if usd_qty>0:
#                 square_order(s,"USD","MARKET","SELL",usd_qty,usd,max_qty,inventory,limit_orders)
#         elif spread>=spread_limit[1]:
            order_type="LIMIT"
            order_size=step_size*0.2
            price_bull=bull-spread/1.5
            price_bear=bear-spread/1.5
            place_order(s,"BULL",order_type,"BUY",order_size,price_bull,max_qty,inventory,limit_orders,inventory_loss)
            place_order(s,"BEAR",order_type,"BUY",order_size,price_bear,max_qty,inventory,limit_orders,inventory_loss)
            if ritc_qty>0:
                square_order(s,"RITC","LIMIT","SELL",ritc_qty,ritc+spread,max_qty,inventory,limit_orders)
        else:
            order_type="LIMIT"
            order_size=step_size*0.075
            price_bull=bull-spread/2
            price_bear=bear-spread/2
            place_order(s,"BULL",order_type,"BUY",order_size,price_bull,max_qty,inventory,limit_orders,inventory_loss)
            place_order(s,"BEAR",order_type,"BUY",order_size,price_bear,max_qty,inventory,limit_orders,inventory_loss)
            if ritc_qty>0:
                square_order(s,"RITC","LIMIT","SELL",ritc_qty,ritc+spread,max_qty,inventory,limit_orders)
        
            
            
            
    elif diff<-0.2:
        spread=max(0.02,abs(diff*quote/100))
        price_ritc=ritc
        price_usd=usd
        bull_qty=inventory["BULL"]
        bear_qty=inventory["BEAR"]
        if spread>=spread_limit[0]:
            order_type="MARKET"
            order_size=step_size*0.2
            place_order(s,"RITC",order_type,"BUY",order_size,price_ritc,max_qty,inventory,limit_orders,inventory_loss)
            #place_order(s,"USD",order_type,"BUY",order_size,price_usd,max_qty,inventory,limit_orders,inventory_loss)
            if bull_qty>0:
                square_order(s,"BULL","MARKET","SELL",bull_qty,bull+spread,max_qty,inventory,limit_orders)
            if bear_qty>0:
                square_order(s,"BEAR","MARKET","SELL",bear_qty,bear+spread,max_qty,inventory,limit_orders)
        elif spread>=spread_limit[1]:
            order_type="LIMIT"
            order_size=step_size*0.1
            price_ritc=ritc-spread/1.5
            place_order(s,"RITC",order_type,"BUY",order_size,price_ritc,max_qty,inventory,limit_orders,inventory_loss)
            if bull_qty>0:
                square_order(s,"BULL","LIMIT","SELL",bull_qty,bull+spread,max_qty,inventory,limit_orders)
            if bear_qty>0:
                square_order(s,"BEAR","LIMIT","SELL",bear_qty,bear+spread,max_qty,inventory,limit_orders)
        
        else:
            order_type="LIMIT"
            order_size=step_size*0.05
            price_ritc=ritc-spread/2
            place_order(s,"RITC",order_type,"BUY",order_size,price_ritc,max_qty,inventory,limit_orders,inventory_loss)
            if bull_qty>0:
                square_order(s,"BULL","LIMIT","SELL",bull_qty,bull+spread,max_qty,inventory,limit_orders)
            if bear_qty>0:
                square_order(s,"BEAR","LIMIT","SELL",bear_qty,bear+spread,max_qty,inventory,limit_orders)
        
        
            
            
def check_limit_orders(s,tick,limit_orders,max_holding_time,inventory):
    print("Inside check_limit_orders")
    if len(limit_orders)>=1:
        #print(limit_orders)
        temp=list(limit_orders.keys())
        for order_id in temp:
            #print(order_id)
            #print(limit_orders[order_id])
            link='http://localhost:9999/v1/orders/' + str(order_id)
            resp=s.get(link)
            #print(resp)
            if  resp.ok:            
                lmt_order = resp.json()    
                #print("hi")
                print(lmt_order)
                if lmt_order['status'] == "OPEN":
                    if (tick-limit_orders[order_id])>max_holding_time:
                        resp_cancel=s.delete(link)
                        
                        if resp_cancel.ok:
                            del limit_orders[order_id]
                            
                            print("LIMIT order for too long")
                        else:
                            print("Cound not cabce")
                else:
                    if lmt_order['action']=="BUY":
                        inventory[lmt_order['ticker']]+=lmt_order['quantity']
                    else:
                        inventory[lmt_order['ticker']]-=lmt_order['quantity']
            else:
                print("Check_limit failed")

def get_max_limits(s):
    max_qty=150000
    print("Max limits")
    resp=s.get('http://localhost:9999/v1/limits')
    if resp.ok:
        limits_json = resp.json()
        for i in limits_json:
            if i['name']=="LIMIT-CASH":
                max_qty=min(max_qty, i['net_limit']/17.5)  
            else:
                max_qty=min(max_qty, i['net_limit'])  
    return max_qty
    
    
    
    

def main():     
    with requests.Session() as s: 
        quote=float(sys.argv[1]) ## 10%
        step_size=float(sys.argv[2])  ## 10000
        max_holding_time=float(sys.argv[3])  ## 5
        inventory_loss=float(sys.argv[4]) ## 0.5
        spread_1=float(sys.argv[4]) ## 0.1
        spread_2=float(sys.argv[5]) ## 0.05
        
        spread_limit=[spread_1,spread_2]
        float(sys.argv[4]) ## 0.5
        inventory={"BULL" : 0, "BEAR" : 0,"USD" : 0, "RITC" :0  }
        API_KEY = {'X-API-key': '8SL0Q95A'} 
        limit_orders={}
        s.headers.update(API_KEY)
        tick=get_tick(s)
        max_qty=get_max_limits(s)
        print(max_qty)
        while tick<=5:
            tick=get_tick(s)
            pass
        while tick>5 and tick<295:
            BULL_bid, BULL_ask=ticker_bid_ask(s,'BULL')
            BEAR_bid, BEAR_ask=ticker_bid_ask(s,'BEAR')
            RITC_bid, RITC_ask=ticker_bid_ask(s,'RITC')
            USD_bid, USD_ask=ticker_bid_ask(s,'USD')
            CAD_bid, CAD_ask=ticker_bid_ask(s,'CAD')
            print("USD")
            print(USD_bid, USD_ask)
            print((USD_bid+USD_ask)/2)
            print("CAD")
            print(CAD_bid, CAD_bid)
            etf_arb( s,(BULL_bid+BULL_ask)/2, (BEAR_bid+BEAR_ask)/2, (RITC_bid+RITC_ask)/2, (USD_bid+USD_ask)/2,quote,max_qty,inventory,limit_orders,inventory_loss,step_size,spread_limit) 
            
            check_limit_orders(s,float(tick),limit_orders,max_holding_time,inventory)
            tick=get_tick(s)
            
            
if   __name__ == '__main__':     
    main()
   
