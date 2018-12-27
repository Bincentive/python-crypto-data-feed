import os
import sys
import time
import datetime
import signal
import pandas as pd
import dateutil.parser
import asyncio
import ccxt.async_support as ccxt
from threading import Thread
import json

def set_fetch_step(timeframe):
    '''
    Set the fetch step based on the timeframe.
    '''
    msec = 1000
    minute = 60 * msec
    hour = 60 * minute
    day = 24 * hour
    
    if(timeframe == '1m'):
        step = minute
    elif(timeframe == '5m'):
        step = minute * 5
    elif(timeframe == '15m'):
        step = minute * 15
    elif(timeframe == '30m'):
        step = minute * 30
    elif(timeframe == '1h'):
        step = hour
    elif(timeframe == '1d'):
        step = day
        
    return step

def set_filepath(exchange,exchange_name,currency,timeframe,start,step):
    '''
    filedir,filepath,deal with timestamp,deal with dataframe 
    '''
    filename = '{}-{}-{}.csv'.format(exchange_name,currency.replace('/','-'),timeframe)
    
    DATASET_PATH = os.environ.get('DATASET_PATH', 'dataset')
    DATASET_NAME = os.environ.get('DATASET_NAME', filename)
    DATASET = os.path.join(DATASET_PATH, DATASET_NAME)

    if os.path.exists(DATASET):
        df_origin = pd.read_csv(DATASET)
        date_str_start = (df_origin['Date'] + ' ' + df_origin['Time']).iloc[0]
        date_str_end = (df_origin['Date'] + ' ' + df_origin['Time']).iloc[-1]
        from_timestamp = exchange.parse8601(date_str_end) + step
        
        if (exchange.parse8601(start) > from_timestamp):
            from_timestamp = exchange.parse8601(start)
    else:
        df_origin = pd.DataFrame(columns = ['Date','Time','Open','High','Low','Close','Volume'])
        date_str_start = start
        from_timestamp = exchange.parse8601(date_str_start)
       
    return from_timestamp, filename, DATASET, df_origin,date_str_start

def save_data_to_csv(exchange,data,DATASET,df_origin,save = 0,save_temp = False):
    '''
    Save data to our file path.
    input:
        exchange:exchange, ccxt.exchange_name()
        data:list, the ohlcv data we fetched.
        DATASET:string, the file path we want to save the data.
        df_origin:dataframe, the origin data we stored.
        save:int default 0, the storage range.
        save_temp:boolean default False, if it's True,it will return save(int).
    output:
        save(int) or None
    '''
    if(len(data) > save*1000):
        # update save
        save += 1

        # transform data to dataframe
        df = pd.DataFrame(data=data,columns=['Timestamp','Open','High','Low','Close','Volume'])
        df['Timestamp'] = df['Timestamp'].apply(exchange.iso8601)

        # split timestamp to date and time to fit the multicharts data form
        time_pair = df['Timestamp'].map(lambda x:dateutil.parser.parse(x).strftime("%Y-%m-%d %H:%M:%S").split(' '))
        temp = pd.DataFrame(columns = ['Date','Time'])
        temp['Date'] = time_pair.map(lambda x:x[0])
        temp['Time'] = time_pair.map(lambda x:x[1])

        df_con = pd.concat([temp,df.drop(['Timestamp'],axis = 1)],axis = 1)
        df_con['Volume'] = df_con['Volume'].apply(int) # the volume data should be int

        # save to file
        df_con = pd.concat([df_origin,df_con],axis = 0).set_index('Date')
        df_con.to_csv(DATASET)
    
    if save_temp:
        return save   
    
def save_dataname_to_json(filename,start,end):
    '''
    Save finished data to json file which named datta_record.
    input:
        filename:string
        start:string, record the start time of the data
        end:string, record the end time of the data
    output:
        None
    '''
    
    DATASET_PATH = os.environ.get('DATASET_PATH', 'dataset')
    DATASET_RECORD = os.path.join(DATASET_PATH,'data_record.json')
    
    # load json file
    if os.path.exists(DATASET_RECORD):
        with open(DATASET_RECORD,'r') as fp:
            data_record = json.load(fp)
    else:
        data_record = {}
    
    # write json file
    with open(DATASET_RECORD, 'w') as fp:
            
        # split filename 
        name_list = filename[:-4].split('-')
        exchange = name_list[0]
        currency = name_list[1]+'/'+name_list[2]
        timeframe = name_list[3]

        # save to dictionary
        
        # save exchange
        if not exchange in data_record.keys():
            data_record[exchange] = {}
        
        # save currency
        if not currency in data_record[exchange].keys():
            data_record[exchange][currency] = {}
        
        # save timeframe
        if not timeframe in data_record[exchange][currency].keys():
            data_record[exchange][currency][timeframe] = {}
        
        # save start time and end time
        data_record[exchange][currency][timeframe]['start'] = start
        data_record[exchange][currency][timeframe]['end'] = end
        
        # save dictionary to json
        json.dump(data_record,fp) 
                     
async def fetch_ohlcv(exchange_name,currency = 'BTC/USDT',timeframe = '1d',start = '2017-01-01 00:00:00'):
    '''
    Start to fetch ohlcv data asynchronously into csv file.
    input:
        exchange_name:string, the name of the exchange(e.g. binance,bitfinex )(lowercase letters)
        currency:string, the currency you want to crawl
        timeframe:string, the timeframe you want(e.g. '1d' '30m')
        start:string, the time you start to crawl
    output:
        None, just print the process for your crawling
    '''
    # set step
    step = set_fetch_step(timeframe)
    # set exchange
    exchange = getattr(ccxt,exchange_name)({
        'rateLimit': 10000,  # set the delay between two http resquest to avoid the ratelimit of exchange
        'enableRateLimit': True, # activate the rateLimit function
        # 'verbose': True,
    })
    # set filepath
    from_timestamp, filename, DATASET, df_origin,start = set_filepath(exchange,exchange_name,currency,timeframe,start,step)
   
    # get ohlcv data
    save = 1
    hold = 10
    data = []
    now = exchange.milliseconds()
    while from_timestamp < now:

        try:
            print(exchange.milliseconds(), 'Fetching candles starting from', exchange.iso8601(from_timestamp),'Data from',filename[:-3])
            ohlcvs = await exchange.fetch_ohlcv(currency, timeframe, from_timestamp)
            print(exchange.milliseconds(), 'Fetched', len(ohlcvs), 'candles')
            first = ohlcvs[0][0]
            last = ohlcvs[-1][0]
            print('First candle epoch', first, exchange.iso8601(first))
            print('Last candle epoch', last, exchange.iso8601(last))
            
            # update timestamp
            from_timestamp = last + step
            data += ohlcvs

        except (ccxt.ExchangeError, ccxt.AuthenticationError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as error:
            print('Got an error', type(error).__name__, error.args, ', retrying in', hold, 'seconds...')
            await asyncio.sleep(hold)
        
        finally:
            # save data during fetching
            save = save_data_to_csv(exchange,data,DATASET,df_origin,save,True)
    
    save_data_to_csv(exchange,data,DATASET,df_origin)
    save_dataname_to_json(filename,start,dateutil.parser.parse(exchange.iso8601(now)).strftime("%Y-%m-%d %H:%M:%S"))
    print(filename[:-3],'Completed')
    await exchange.close()
    
def start_loop(loop):
    '''
    Open a new event loop.
    '''
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Just use this function to crawl data.
def start_fetch_ohlcv(exchange_name,currency,timeframe,start):
    '''
    Start to fetch the ohlcv.
    input:
        exchange_name:list, exchange names
        currency:list
        timeframe:list
        start:list
    ps: The length of the input should be the same.(one to one mapping)
    '''
    new_loop = asyncio.new_event_loop()
    t = Thread(target=start_loop, args=(new_loop,))
    t.start()
    
    for e,c,t,f in zip(exchange_name,currency,timeframe,start):
        asyncio.run_coroutine_threadsafe(fetch_ohlcv(e,c,t,f), new_loop)
    new_loop.close()