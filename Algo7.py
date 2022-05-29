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
    quantity=qty*inventory_loss
    resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': "MARKET", 'quantity': quantity, 'action': side })
    if resp.ok:              
        print("The lose inventory "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity)  )   
    else:            
        print("lose_inventory failed")
    
    
def place_order(s,ticker,order_type,side,quantity,price,max_qty,inventory,limit_orders,inventory_loss):
    print("Inside place_order")
    qty=inventory[ticker]
    if qty>=max_qty or qty<=-1*max_qty:
        print("Too much invenotry")
        lose_inventory(s,ticker,qty,inventory_loss)
#     if ticker=="USD" and (qty>=max_qty or qty<=-1*max_qty):
#         print("Too many USD")
#         lose_inventory(s,ticker,qty,inventory_loss)
    else:
        if order_type=="MARKET":
            resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': order_type, 'quantity': quantity, 'action': side })
            if   resp.ok:            
                mkt_order = resp.json()            
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

                
                
def etf_arb(s,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask, RITC_bid,RITC_ask, USD_bid,USD_ask,CAD_bid, CAD_ask,quote,max_qty,inventory,limit_orders,inventory_loss,step_size,spread_limit):
    bull=(BULL_bid+BULL_ask)/2
    bear=(BEAR_bid+BEAR_ask)/2
    usd=(USD_bid+USD_ask)/2
    ritc=(RITC_bid+RITC_ask)/2
    
    print("Inside etf_arb")
    diff = ritc*usd - (bull + bear)
    if diff>0.02:
        spread=max(0.03,diff*quote/100)
        ritc_qty=inventory["RITC"]
        usd_qty=inventory["USD"]
        print(spread,diff,diff*quote/100)
        if spread>=spread_limit[0]:
            print("fd")
            order_type="MARKET"
            order_size=step_size*0.2
            place_order(s,"BULL",order_type,"BUY",order_size,BULL_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
            place_order(s,"BEAR",order_type,"BUY",order_size,BEAR_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
            cad_quantity=(BULL_bid-spread+BEAR_bid-spread)*order_size
            #place_order(s,"CAD","LIMIT","SELL", cad_quantity,CAD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
            
            if ritc_qty>0:
                place_order(s,"RITC",order_type,"SELL",2*order_size,RITC_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
                usd_quantity=(RITC_ask+spread)*ritc_qty
                #place_order(s,"USD","LIMIT","BUY",usd_quantity,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
                
                #square_order(s,"USD","MARKET","BUY",usd_qty,ritc+spread,max_qty,inventory,limit_orders)
                
            
#             if inventory['USD']< 1*(order_size*(BULL_bid-spread+BEAR_bid-spread)) + order_size*(RITC_ask+spread):
#                 usd_quantity=(order_size*(BULL_bid-spread+BEAR_bid-spread)) + order_size*(RITC_ask+spread)-inventory['USD']
#                 place_order(s,"USD","LIMIT","BUY",usd_quantity,USD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
#             else:
#                 usd_quantity=inventory['USD']- (order_size*(BULL_bid-spread+BEAR_bid-spread)) - order_size*(RITC_ask+spread) 
#                 place_order(s,"USD","LIMIT","SELL",usd_quantity,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
#             if usd_qty>0:
#                 square_order(s,"USD","MARKET","SELL",usd_qty,usd,max_qty,inventory,limit_orders)
        elif spread>=spread_limit[1]:
            order_type="LIMIT"
            order_size=step_size*0.1
            #price_bull=bull-spread/1.5
            #price_bear=bear-spread/1.5
            place_order(s,"BULL",order_type,"BUY",order_size,BULL_bid-spread/1.5,max_qty,inventory,limit_orders,inventory_loss)
            place_order(s,"BEAR",order_type,"BUY",order_size,BEAR_bid-spread/1.5,max_qty,inventory,limit_orders,inventory_loss)
            if ritc_qty>0:
                place_order(s,"RITC",order_type,"SELL",2*order_size,RITC_ask+spread/1.5,max_qty,inventory,limit_orders,inventory_loss)
        else:
            order_type="LIMIT"
            order_size=step_size*0.05
            price_bull=bull-spread/2
            price_bear=bear-spread/2
            place_order(s,"BULL",order_type,"BUY",order_size,BULL_bid-spread/2,max_qty,inventory,limit_orders,inventory_loss)
            place_order(s,"BEAR",order_type,"BUY",order_size,BEAR_bid-spread/2,max_qty,inventory,limit_orders,inventory_loss)
            if ritc_qty>0:
                place_order(s,"RITC",order_type,"SELL",2*order_size,RITC_ask+spread/2,max_qty,inventory,limit_orders,inventory_loss)
        
            
            
            
    elif diff<-0.2:
        spread=max(0.03,abs(diff*quote/100))
        price_ritc=ritc
        price_usd=usd
        bull_qty=inventory["BULL"]
        bear_qty=inventory["BEAR"]
        print(spread,diff,diff*quote/100)
        if spread>=spread_limit[0]:
            order_type="MARKET"
            print("fd2")
            order_size=step_size*0.2
            place_order(s,"RITC",order_type,"BUY",order_size,RITC_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
            #place_order(s,"USD","LIMIT","SELL",order_size*(RITC_bid-spread),USD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
            if bull_qty>0:
                place_order(s,"BULL",order_type,"SELL",order_size/2,BULL_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
                #place_order(s,"CAD","LIMIT","BUY",bull_qty*(BULL_ask+spread),CAD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
            if bear_qty>0:
                place_order(s,"BEAR",order_type,"SELL",order_size/2,BEAR_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
                #place_order(s,"CAD","LIMIT","BUY",bear_qty*(BEAR_ask+spread),CAD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
            
#             if inventory['USD']< (order_size*(BEAR_ask+spread+BULL_ask+spread)) + order_size*(RITC_bid-spread):
#                 usd_quantity=(order_size*(BEAR_ask+spread+BULL_ask+spread)) + order_size*(RITC_bid-spread)-inventory['USD']
#                 place_order(s,"USD","LIMIT","SELL",usd_quantity,USD_bid-spread,max_qty,inventory,limit_orders,inventory_loss)
#             else:
#                 usd_quantity=inventory['USD']- (order_size*(BEAR_ask+spread+BULL_ask+spread)) + order_size*(RITC_bid-spread)
#                 place_order(s,"USD","LIMIT","BUY",usd_quantity,USD_ask+spread,max_qty,inventory,limit_orders,inventory_loss)
            
                #place_order(s,"CAD","MARKET","BUY",order_size,price_bear,max_qty,inventory,limit_orders,inventory_loss)
        elif spread>=spread_limit[1]:
            order_type="LIMIT"
            order_size=step_size*0.1
            #price_ritc=ritc-spread/1.5
            place_order(s,"RITC",order_type,"BUY",order_size,RITC_bid-spread/1.5,max_qty,inventory,limit_orders,inventory_loss)
            if bull_qty>0:
                place_order(s,"BULL",order_type,"SELL",order_size/2,BULL_ask+spread/1.5,max_qty,inventory,limit_orders,inventory_los)
            if bear_qty>0:
                place_order(s,"BEAR",order_type,"SELL",order_size/2,BEAR_ask+spread/1.5,max_qty,inventory,limit_orders,inventory_los)
        
        else:
            order_type="LIMIT"
            order_size=step_size*0.05
            #price_ritc=ritc-spread/2
            place_order(s,"RITC",order_type,"BUY",order_size,RITC_bid-spread/2,max_qty,inventory,limit_orders,inventory_loss)
            if bull_qty>0:
                place_order(s,"BULL",order_type,"SELL",order_size/2,BULL_ask+spread/2,max_qty,inventory,limit_orders,inventory_los)
            if bear_qty>0:
                place_order(s,"BEAR",order_type,"SELL",order_size/2,BEAR_ask+spread/2,max_qty,inventory,limit_orders,inventory_los)
        
        
            
            
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
                            print("Cound not cabce")
            else:
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
        
 
def place_tender(s,tenders,tick,tender_id,side,price,qty,inventory,max_qty):
    if side=="BUY":
        if abs( inventory['USD'] -  price*qty)< max_qty['USD'] and abs(qty+inventory['RITC']) < max_qty['RITC']:
            link='http://localhost:9999/v1/tenders/' +str(tender_id)
            resp = s.post(link)
            tend = resp.json()
            if resp.ok:
                tenders[tender_id]=[qty,price,tick]
                print("Tender " + side +  " order placed at " + str(tick) + "  for " +  str(qty) + " at " +str(price) )
        else:
            print("Too many long positions in RITC or USD")
    else:
        if abs(price*qty  + inventory['USD'] )< max_qty['USD'] and abs(-1*qty+inventory['RITC']) < max_qty['RITC']:
            link='http://localhost:9999/v1/tenders/' +str(tender_id)
            resp = s.post(link)
            tend = resp.json()
            if resp.ok:
                tenders[tender_id]=[-1*qty,price,tick]
                print("Tender " + side +  " order placed at " + str(tick) + "  for " +  str(qty) + " at " +str(price) ) 
        else:
            print("Too many short positions in RITC or USD")
    
def RSI(spread,n):
    
    df = pd.DataFrame()
    df['spread']=spread
    df['delta']=df['spread'] - df['spread'].shift(1)
    df['gain']=np.where(df['delta']>=0,df['delta'],0)
    df['loss']=np.where(df['delta']<0,abs(df['delta']),0)
    avg_gain = []
    avg_loss = []
    gain = df['gain'].tolist() 
    loss = df['loss'].tolist()
    for i in range(len(df)):
        if i < n:
            avg_gain.append(np.NaN)
            avg_loss.append(np.NaN)
        elif i == n:
            avg_gain.append(df['gain'].rolling(n).mean().tolist()[n])
            avg_loss.append(df['loss'].rolling(n).mean().tolist()[n])
        elif i > n:
            avg_gain.append(((n-1)*avg_gain[i-1] + gain[i])/n)
            avg_loss.append(((n-1)*avg_loss[i-1] + loss[i])/n)
    df['avg_gain']=np.array(avg_gain)
    df['avg_loss']=np.array(avg_loss)
    df['RS'] = df['avg_gain']/df['avg_loss']
    df['RSI'] = 100 - (100/(1+df['RS']))
    df = df.drop(['delta','gain','loss','avg_gain','avg_loss','RS'],axis=1)
    df.dropna(inplace=True)
    return list(df['RSI'])[-1]
    

    
      
    

def check_tenders(s,tenders,tick,limit_orders,max_holding_time, inventory, max_qty, BULL_bid,BULL_ask, BEAR_bid, BEAR_ask, RITC_bid,RITC_ask, USD_bid,USD_ask,spread,n,convertor):
    
    ritc=(RITC_bid+RITC_ask)/2
    bear=(BEAR_bid+BEAR_ask)/2
    bull=(BULL_bid+BULL_ask)/2
    usd=(USD_bid+USD_ask)/2
    print("RITC")
    print(RITC_bid,RITC_ask)
    print("BULL")
    print(BULL_bid,BULL_ask)
    print("BEAR")
    print(BEAR_bid,BEAR_ask)
    print("USD")
    print(USD_bid,USD_ask)

    diff = ritc - (bull + bear)
   
    if len(spread)==0:
        spread.append(diff)
    elif spread[-1]!=diff:
        spread.append(diff)
        
    if len(spread)>=(n+1):
        spread_avg=sum(spread[-n:])/len(spread[-n:])
        RSI_val=RSI(spread[-n-1:],n)
        print("RSI,doff")
        print(RSI_val,diff)
        resp = s.get('http://localhost:9999/v1/tenders')
        tend = resp.json()
        if resp.ok:
            for i in tend:
                if i['is_fixed_bid']==True:
                    if i['action']=="BUY":
#                         temp=i['quantity']-i['quantity']%10000
# #                         if (temp*BEAR_bid + temp*BULL_bid-1500*USD_ask)>(i['price']*temp-25000) :
# #                             print("USE etf redemption convert")
# #                             convertor[0]=True
#                             place_tender(s,tenders,tick,i['tender_id'],i['action'], i['price'],i['quantity'],inventory,max_qty )
                        if RITC_ask-i['price']>0.05 and diff<-0.1:
                            place_tender(s,tenders,tick,i['tender_id'],i['action'], i['price'],i['quantity'],inventory,max_qty )
                        else:
                            link='http://localhost:9999/v1/tenders/' +str(i['tender_id'])
                            resp = s.delete(link)
                            tend = resp.json()
                            if resp.ok:
                                print("Tender declined")

                    else:
                        if i['price']-RITC_bid>0.05 and diff>0.1 :                            
                            place_tender(s,tenders,tick,i['tender_id'],i['action'], i['price'],i['quantity'],inventory,max_qty)
                        else:
                            link='http://localhost:9999/v1/tenders/' +str(i['tender_id'])
                            resp = s.delete(link)
                            tend = resp.json()
                            if resp.ok:
                                print("Tender declined")

                    
                    
        
        
    
def empty_tenders(s,tick,tenders,inventory,max_qty,RITC_bid, RITC_ask,limit_orders,USD_bid,USD_ask,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask,convertor):
    ticker="RITC"
    flag=0
    ten_keys=list(tenders.keys())
    
#     if convertor[0]==True:
#         for ten in ten_keys:
#             if tenders[ten][0]>0:
#                 side="SELL"
#                 side_usd="BUY"
#                 if inventory['RITC']>0:
#                     flag=1
#                 step_usd=(USD_bid-USD_ask)/8
#                 price=RITC_ask
#                 price2=RITC_bid
#                 price_bull=BULL_ask
#                 price_bull2=BULL_bid
#                 price_bear=BEAR_ask
#                 price_bear2=BEAR_bid
                
#                 step_ritc=(RITC_bid-RITC_ask)/8
#                 step_bull=(BULL_bid-BULL_ask)/8
#                 step_bear=(BEAR_bid-BEAR_ask)/8
#             else:
#                 side="BUY"
#                 side_usd="SELL"
#                 if inventory['RITC']<0 :
#                     flag=1
#                 price=RITC_bid
#                 price2=RITC_ask
#                 price_bull2=BULL_ask
#                 price_bull=BULL_bid
#                 price_bear2=BEAR_ask
#                 price_bear=BEAR_bid
                
#                 step_usd=(USD_ask-USD_bid)/8
#                 step_ritc=(RITC_ask-RITC_bid)/8
#                 step_bull=(BULL_ask-BULL_bid)/8
#                 step_bear=(BEAR_ask-BEAR_bid)/8
                
#             quantity_remaining=abs(inventory['RITC'])%10000
#             quantity=abs(tenders[ten][0])-quantity_remaining
#             max_size=10000 
#             resp = s.post('http://localhost:9999/v1/orders', params={'ticker':"RITC", 'type': "MARKET", 'quantity': max_size, 'action': side_usd })
#             if flag==1:
#                 i=1
#                 if inventory['BULL']!=0 and inventory['BEAR']!=0:
#                     while inventory['BULL']>=max_size:
#                         resp = s.post('http://localhost:9999/v1/orders', params={'ticker': "BULL", 'type': "LIMIT", 'quantity': max_size, 'action': side , 'price':max(price_bull + i*step_bull, price_bull2 -2*step_bull)  })
#                         resp = s.post('http://localhost:9999/v1/orders', params={'ticker': "BEAR", 'type': "LIMIT", 'quantity': max_size, 'action': side , 'price': max(price_bear + i*step_bear, price_bear2 -2*step_bear) })
#                         if resp.ok:        
#                             print("Empty Tender limit for"  +str(side)+ " was submitted for BULL and BEAR"  + " for "  +  str(max_size) + "qty at" + str(price + i*step_ritc ))  

#                         else:            
#                             print("Empty tender failed for innner loop")
#                         inventory['BULL']-=max_size
#                         inventory['BEAR']-=max_size
#                         i+=1
                    
#                     if resp.ok:
#                         if ten in tenders:
#                             if inventory['RITC']==0:
                                
#                                 del tenders[ten]
                    
#             else:
#                 print("Tender not yet executed")

#     elif convertor[0]==False:
    for ten in ten_keys:
        if tenders[ten][0]>0:
            side="SELL"
            side_usd="BUY"
            if inventory['RITC']>0:
                flag=1
            step_usd=(USD_bid-USD_ask)/5
            price=RITC_ask
            price2=RITC_bid
            step_ritc=(RITC_bid-RITC_ask)/5
        else:
            side="BUY"
            side_usd="SELL"
            if inventory['RITC']<0 :
                flag=1
            price=RITC_bid
            price2=RITC_ask
            step_usd=(USD_ask-USD_bid)/5
            step_ritc=(RITC_ask-RITC_bid)/5
        quantity=abs(tenders[ten][0])
        max_size=10000 
        max_size_usd=2500000
        i=2
        if flag==1:
            while quantity>=max_size:
                resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': "LIMIT", 'quantity': max_size, 'action': side , 'price': price + 0.5*step_ritc })

                if resp.ok:        
                    print("Empty Tender limit for"  +str(side)+ " was submitted for " + str(ticker) + " for "  +  str(max_size) + "qty at" + str(price + i*step_ritc ))  
                    if inventory['USD']>0:
                        inventory['USD']-=max_size*(price + i*step_ritc)
                    else:
                        inventory['USD']+=max_size*(price + i*step_ritc)

                else:            
                    print("Empty tender failed for innner loop")
                quantity-=max_size
                i+=1

            if inventory['USD']>0:
                resp = s.post('http://localhost:9999/v1/orders', params={'ticker': "USD", 'type': "MARKET", 'quantity': inventory['USD'], 'action': "SELL" , 'price': USD_ask-step_usd })   
                print("USD remianinng sell order for " + str(inventory['USD']) )
            else:
                resp = s.post('http://localhost:9999/v1/orders', params={'ticker': "USD", 'type': "MARKET", 'quantity': abs(inventory['USD']), 'action': "BUY" , 'price': USD_bid+step_usd })  
                print("USD remianinng buy order for " + str(abs(inventory['USD'])) )

            resp = s.post('http://localhost:9999/v1/orders', params={'ticker': ticker, 'type': "LIMIT", 'quantity': quantity, 'action': side, 'price': max(price + step_ritc, price2 -i*step_ritc)  })


            if resp.ok:              
                print("The Empty "  +str(side)+ "order was submitted for " + str(ticker) + " for "  +  str(quantity)  )  
                if ten in tenders:
                    del tenders[ten] 
            else:            
                print("Empty tender failed for last qty")
        else:
            print("Tender not yet executed")
             


def qty_level(s,ticker,side):
    q=10000
    p={'ticker':ticker, 'limit':2}
    resp=s.get('http://localhost:9999/v1/limits/securities/book')
    if resp.ok:
        book=resp.json()
        if side=="BUY":
            q=book['bids'][0]['quantity']
        else:
            q=book['asks'][0]['quantity']
        return q
        
    raise ApiException("Error")
            
            
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
        tenders={}
        spread=[]
        n=10
        convertor={}
        convertor[0]=False
        while tick>5 and tick<295:
            
#             print("tick is " + str(tick))
#             print("inventory")
#             print(inventory)
            BULL_bid, BULL_ask=ticker_bid_ask(s,'BULL')
            BEAR_bid, BEAR_ask=ticker_bid_ask(s,'BEAR')
            RITC_bid, RITC_ask=ticker_bid_ask(s,'RITC')
            USD_bid, USD_ask=ticker_bid_ask(s,'USD')
            CAD_bid, CAD_ask=ticker_bid_ask(s,'CAD')
            #spread=max(0.02,abs(diff)*quote/100)
    

            #etf_arb( s,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask, RITC_bid,RITC_ask, USD_bid,USD_ask,CAD_bid, CAD_ask,quote,max_qty,inventory,limit_orders,inventory_loss,step_size,spread_limit) 
            get_inventory(s,inventory)
            #check_currency_pos(s,inventory,max_qty,limit_orders,USD_bid,USD_ask,spread,inventory_loss,currency_spread)
            tick_arr.append(tick)

        #check_limit_orders(s,tick,limit_orders,max_holding_time,inventory)  
            get_inventory(s,inventory)
            check_tenders(s,tenders,tick,limit_orders,max_holding_time,inventory,max_qty,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask, RITC_bid,RITC_ask, USD_bid,USD_ask,spread,n,convertor)
            if len(tenders)>=1:
                empty_tenders(s,tick,tenders,inventory,max_qty,RITC_bid, RITC_ask,limit_orders,USD_bid,USD_ask,BULL_bid,BULL_ask, BEAR_bid, BEAR_ask,convertor)
            check_limit_orders(s,tick,limit_orders,max_holding_time,inventory)
            print("------------------------------------------------------------------------------------------------------")

            tick=get_tick(s)
            
            
if   __name__ == '__main__':     
    main()
   
