import requests, Crypto, base64, json, re, certifi, logging, time
from threading import Thread
from queue import Queue, Empty
from datetime import datetime, timezone
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Cipher import PKCS1_OAEP
from collections import OrderedDict
from requests.exceptions import ConnectTimeout


class CheckoutThread(Thread):
    def __init__(self, cart_queue, proxy=False):
        Thread.__init__(self, daemon=True)
        self.q = cart_queue
        self.LOGIN_EMAIL = 'shoppingford@live.com'
        self.LOGIN_PASSWORD = 'Jomab0By'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36 Edg/85.0.564.63'
        self.PHONE = '8016369940'
        self.RETRY_WAIT = 3
        self.LOGIN_CHECK = 1*60
        
        self.s = requests.Session()
        self.s.headers.update({
            'User-Agent': self.USER_AGENT, 
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 
            'Accept-Language': 'en-US,en;q=0.9',
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Dest": "empty",
            })

        # Optional - proxy
        if(proxy):
            with open('burp.pem', 'rb') as certfile:
                customca = certfile.read()
            with open(certifi.where(), 'ab') as outfile:
                outfile.write(customca)

            proxies = {
                'http': 'http://10.10.10.129:8080',
                'https': 'http://10.10.10.129:8080'
            }
            self.s.proxies = proxies

    def run(self):
        # Startup
        last_logged_in = 0

        # Loop checking the queue
        while True:
            try:
                # Check login status
                if time.time() - last_logged_in > self.LOGIN_CHECK:
                    if not self._check_login():
                        if not self._login():
                            # Wait for a few seconds and try again
                            time.sleep(self.RETRY_WAIT)
                            continue

                    last_logged_in = time.time()

                # Check queue
                time_to_block = (last_logged_in + self.LOGIN_CHECK) - time.time()
                try:
                    job = self.q.get(timeout=time_to_block)
                    self._do_job(job)
                    self.q.task_done()

                except Empty:
                    logging.warn("Nothing in the queue")
                    continue
            except ConnectTimeout as e:
                logging.error("Request timeout: {}".format(e))

    def _do_job(self, job):
        logging.info("Got a job from the queue: {}".format(job))

        url, sku, limit, want, temp_q = job
        num_try = min(want, limit)
        num_cart = 0
        for _ in range(num_try):
            # Get OPTIONS
            ts = requests.Session()
            proxies = {
                'http': 'http://10.10.10.129:8080',
                'https': 'http://10.10.10.129:8080'
            }
            ts.proxies = proxies
            headers = OrderedDict({
                'Connection': 'keep-alive',
                'Accept': '*/*', 
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
                'Origin': 'https://api.bestbuy.com',
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Dest": "empty",
                'Referer': 'https://api.bestbuy.com/click/-/{}/cart'.format(sku),
                'User-Agent': self.USER_AGENT,
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            ts.headers = headers
            req_post = requests.Request('OPTIONS', 'https://www.bestbuy.com/cart/api/v1/addToCart')
            req_post_prep = ts.prepare_request(req_post)
            del req_post_prep.headers['Content-Length']
            ts.send(req_post_prep)

            d = {'items': [{"skuId":str(sku)}]}

            headers = OrderedDict({
                'Connection': 'keep-alive',
                'Accept': 'application/json', 
                'Content-Type': 'application/json; charset=UTF-8',
                'Origin': 'https://api.bestbuy.com',
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Dest": "empty",
                'Referer': 'https://api.bestbuy.com/click/-/{}/cart'.format(sku),
                'User-Agent': self.USER_AGENT,
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'en-US,en;q=0.9',
            })

            while True:
                try:
                    req_cart = self.s.post('https://www.bestbuy.com/cart/api/v1/addToCart', data=json.dumps(d, separators=(',',':')), headers=headers, timeout=5)
                    if req_cart.status_code == 200:
                        break
                except Exception:
                    print("timed out")
                    continue



            #req_cart = ts.post('https://www.bestbuy.com/cart/api/v1/addToCart', data=json.dumps(d, separators=(',',':')))
            print(req_cart)
            print(req_cart.text)
            if req_cart.status_code == 200:
                num_cart += 1
            else:
                print(req_cart)
                print(req_cart.text)
            
        # Cart is ready, try to checkout

        success = self._checkout()
        number = num_cart
        temp_q.put((success, number))
        return success

    def _checkout(self): 
        req_cart = self.s.get('https://www.bestbuy.com/cart?cmp=RMX', timeout=5)
        print(req_cart)
        print(req_cart.text)
        

        logging.info("this is a placeholder")
        return True

    def _check_login(self):
        req_signin = self.s.get('https://www.bestbuy.com/identity/global/signin', timeout=5)
        assert req_signin.status_code == 200
        log_msg = "Checking login status..."
        if req_signin.request.path_url == '/':
            logging.info(log_msg + " logged in")
            return True
        else:
            logging.info(log_msg + " not logged in")
            return False

    def _login(self):
        try:
            req_signin = self.s.get('https://www.bestbuy.com/identity/global/signin', timeout=5)
            assert req_signin.status_code == 200
            logging.info('Retrieved signin page, building login request')

            # Build authentication request
            auth_data = {}

            ## token:
            token = req_signin.request.path_url.split("token=")[1]
            auth_data['token'] = token

            ## activity
            req_cia_user_activity = self.s.get('https://www.bestbuy.com/api/csiservice/v2/key/cia-user-activity', timeout=5)
            assert req_cia_user_activity.status_code == 200

            cia_activity = {
                'email': self.LOGIN_EMAIL,
                'fieldReceivedFocus': True,
                'fieldReceivedInput': True,
                'keyboardUsed': True,
                'mouseMoved': True,
                'timestamp': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace("+00:00", "Z")
            }

            cia_activity_key = req_cia_user_activity.json()['publicKey']
            cia_activity_keyId = req_cia_user_activity.json()['keyId']
            cia_activity_rsa_key = RSA.importKey(cia_activity_key)
            cia_activity_cipher_rsa = PKCS1_OAEP.new(cia_activity_rsa_key)
            cia_activity_encr = cia_activity_cipher_rsa.encrypt(json.dumps(json.dumps(cia_activity, separators=((",",":")))).encode('ascii'))
            auth_data['activity'] = ':'.join(['1', cia_activity_keyId, base64.b64encode(cia_activity_encr).decode('ascii')])

            ## loginMethod
            auth_data['loginMethod'] = "UID_PASSWORD"

            ## flowOptions
            auth_data['flowOptions'] = "00000000"

            ## alpha
            alphas = re.findall(r"\"alpha\":\[(.*?)\]", req_signin.text)
            if alphas:
                alphas = alphas[0].replace('"', '').split(',')

            alpha_regex = r"^[0-9]+_A_.+$"
            for alpha in alphas:
                alpha_decoded = base64.b64decode(alpha[::-1]).decode('utf8')
                matches = re.search(alpha_regex, alpha_decoded)
                if matches:
                    auth_data['alpha'] = alpha
                    break

            ## Salmon
            salmon = re.findall(r"\"Salmon\":\"(.*?)\"", req_signin.text)
            if salmon:
                auth_data['Salmon'] = salmon[0]

            ## encryptedEmail
            req_cia_email = self.s.get('https://www.bestbuy.com/api/csiservice/v2/key/cia-email', timeout=5)
            assert req_cia_email.status_code == 200

            cia_email_key = req_cia_email.json()['publicKey']
            cia_email_keyId = req_cia_email.json()['keyId']
            cia_email_rsa_key = RSA.importKey(cia_email_key)
            cia_email_cipher_rsa = PKCS1_OAEP.new(cia_email_rsa_key)
            cia_email_encr = cia_email_cipher_rsa.encrypt(self.LOGIN_EMAIL.encode('ascii'))
            auth_data['encryptedEmail'] = ':'.join(['1', cia_email_keyId, base64.b64encode(cia_email_encr).decode('ascii')])


            ## password
            codes = re.findall(r"\"codeList\":\[(.*?)\]", req_signin.text)
            if codes:
                codes = codes[0].replace('"', '').split(',')

            code_regex = r"^\d+_X_.+$"
            for code in codes:
                code_decoded = base64.b64decode(code).decode('ascii')
                matches = re.search(code_regex, code_decoded)
                if matches:
                    auth_data[code] = self.LOGIN_PASSWORD
                    break

            ## info 
            # same as activity but user agent!
            cia_ua_encr = cia_activity_cipher_rsa.encrypt(self.USER_AGENT.encode('ascii'))
            auth_data['info'] = ':'.join(['1', cia_activity_keyId, base64.b64encode(cia_ua_encr).decode('ascii')])

            ## email
            email = re.findall(r"\"emailFieldName\":\"(.*?)\"", req_signin.text)
            if email:
                auth_data[email[0]] = self.LOGIN_EMAIL

            logging.info('Built sign-in request: {}'.format(json.dumps(auth_data, indent=2)))


            req_auth = self.s.post('https://www.bestbuy.com/identity/authenticate', data=auth_data, timeout=5)
            assert req_auth.status_code == 200
            assert self.PHONE not in req_auth.text
            # Best Buy is trying to verify me - manually do this. 

            if req_auth.json()['status'] == 'success':
                logging.info("Successfully logged in: {} ".format(req_auth.status_code))
                logging.debug("Login POST data: {} ".format(req_auth.json()['token']))

                # GET COOKIES
                req_cart = self.s.get('https://www.bestbuy.com/cart/c/?cmp=RMX', timeout=5)
                assert req_cart.status_code == 200
                
                return True

            else:
                logging.error("Could not log in: {}".format(req_auth.text))
                return False
        except Exception as e:
            logging.error("Could not log in: {} - {}".format(type(e), e))


# Keep checking stock until you find one - when found, put it in the queue!    
def stock_checker(q, apikey, sku, count, wait=2):
    while count > 0:
        start_time = time.time()
        r = requests.get("https://api.bestbuy.com/v1/products/{}.json?apiKey={}".format(sku, apikey))
        if r.status_code == 200:
            res = json.loads(r.content)
            limit = res['quantityLimit']
            if res['onlineAvailability']:
                # Try to make a purchase
                logging.info("SKU: {} ({}); available: {}; last upate: {}".format(res['sku'], res['name'], res['onlineAvailability'], res['onlineAvailabilityUpdateDate']))
                temp_q = Queue()
                q.put((
                    res['addToCartUrl'],
                    limit,
                    count,
                    temp_q
                ))
                
                success, number = temp_q.get()
                if success:
                    count -= number
            else:
                logging.debug("SKU: {}; available: {}; last upate: {}".format(res['sku'], res['onlineAvailability'], res['onlineAvailabilityUpdateDate']))
        else:
            logging.warn("Best Buy API request failed: {} - {}".format(r.status_code, r.json()))

        sleep_time = start_time + wait - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
    logging.info("Purchased limit!")


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.INFO)

    checkout_q = Queue(maxsize=0)

    # Setup login/checkout thread
    #checkout_thread = CheckoutThread(checkout_q, proxy=True)
    #checkout_thread.start()


    product_skus = OrderedDict({
        6429434: 10, # 3090 FE
        6434363: 1, # 3090 EVGA
        #6430624: 1, # 3090 Gigabyte
        6429440: 10, # 3080 FE
        6432399: 1, # 3080 EVGA
        6430621: 1, # 3080 Gigabyte
        #6430215: 1,
    })

    bbapikey = 'RxSAGECBoqw9a3ZhHR6ZMojU'
    time_between_calls = .75

    # BB Api call limited to 2 a second (unconfirmed)
    while True:
        # Check all SKUs at once
        time_started = time.time()
        skus = product_skus.keys()
        r = requests.get("https://api.bestbuy.com/v1/products(sku in ({}))?format=json&apiKey={}".format(','.join(map(str, skus)), bbapikey))
        if r.status_code == 200:
            results = r.json()
            products = {product['sku']: product for product in results['products']}

            import webbrowser

            # Go by order of priority and look for stock
            pause = False
            for sku in product_skus:
                print("checking {}".format(sku))
                product = products[sku]
                limit = product['quantityLimit']
                if product['onlineAvailability']:
                    # Try to make a purchase
                    logging.info("SKU: {} ({}); available: {}; last upate: {}".format(sku, product['name'], product['onlineAvailability'], product['onlineAvailabilityUpdateDate']))
                    #temp_q = Queue()
                    # checkout_q.put((
                    #     product['addToCartUrl'],
                    #     sku,
                    #     limit,
                    #     product_skus[sku],
                    #     temp_q
                    # ))
                    
                    # response = ''
                    # out = "PRODUCT: {}|{}|Limit {} - open in browser? [Y]es, S[kip]".format(product['name'], sku, product['quantityLimit'])
                    # r = input(out)

                    print("PRODUCT: {}|{}|Limit {}".format(product['name'], sku, product['quantityLimit']))
                    webbrowser.open(product['addToCartUrl'])
                    pause = True



                    # success, number = temp_q.get()
                    # if success:
                    #     product_skus[sku] -= number
                    #     logging.info("Successfully purchased {} of {}:{} - {} left".format(number, sku, product['name'], product_skus[sku]))
                    #     # Cleanup
                    #     for sku in product_skus.keys():
                    #         if product_skus[sku] <= 0:
                    #             product_skus.pop(sku)
                else:
                    logging.debug("SKU: {} ({}); available: {}; last upate: {}".format(sku, product['name'], product['onlineAvailability'], product['onlineAvailabilityUpdateDate']))
            if pause:
                time.sleep(10)
        else:
            logging.warning("Best Buy API request failed: {} - {}".format(r.status_code, r.json()))
        time_to_wait = time_between_calls - (time.time() - time_started)
        if time_to_wait > 0:
            time.sleep(time_to_wait)
