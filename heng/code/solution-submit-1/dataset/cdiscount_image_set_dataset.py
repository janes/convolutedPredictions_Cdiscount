##  https://www.kaggle.com/c/cdiscount-image-classification-challenge
##  Cdiscount’s Image Classification Challenge
##
##  https://www.kaggle.com/alekseit/pytorch-bson-dataset
##  https://www.kaggle.com/humananalog/keras-generator-for-reading-directly-from-bson



from dataset.transform import *
from dataset.sampler import *
from utility.file import *
from utility.draw import *
import bson
import struct


CDISCOUNT_DIR = '/media/ssd/data/kaggle/cdiscount'
CDISCOUNT_NUM_CLASSES = 5270
CDISCOUNT_HEIGHT=180
CDISCOUNT_WIDTH =180

#
# #data iterator ----------------------------------------------------------------
class CDiscountImageSetDataset(Dataset):

    def __init__(self, split, bson, transform=None, mode='train'):
        super(CDiscountImageSetDataset, self).__init__()
        self.split = split
        self.bson  = bson
        self.mode  = mode
        self.transform = transform

        #label to name
        category_names_df = pd.read_csv (CDISCOUNT_DIR + '/category_names.csv')
        category_names_df['label'] = category_names_df.index
        label_to_category_id = dict(zip(category_names_df['label'], category_names_df['category_id']))
        category_id_to_label = dict(zip(category_names_df['category_id'], category_names_df['label']))

        #dump
        #with open(CDISCOUNT_DIR + '/label_to_category_id.pkl', 'wb') as f: pickle.dump(label_to_category_id, f, pickle.HIGHEST_PROTOCOL)

        self.category_names_df    = category_names_df
        self.label_to_category_id = label_to_category_id
        self.category_id_to_label = category_id_to_label

        #read split
        print('read img list')
        ids = read_list_from_file(CDISCOUNT_DIR + '/split/' + split, comment='#', func=int)
        num_ids = len(ids)


        #read images and labels
        start = timer()
        df = pd.read_csv (CDISCOUNT_DIR + '/%s_by_product_id.csv'%bson)
        #df.columns #(['product_id', 'category_id', 'count', 'offset', 'length'], dtype='object')

        df = df.reset_index()
        df = df[ df['product_id'].isin(ids)]
        #df = df.reindex(np.repeat(df.index.values, df['count']), method='ffill')
        #df['cumcount'] = df.groupby(['product_id']).cumcount()

        if mode=='train':
            df['label'] = df['category_id'].map(category_id_to_label)
            self.labels = list(df['label'])
        elif mode=='test':
            self.labels = None
        else:
            raise NotImplementedError

        assert(num_ids == df['product_id'].nunique())
        num_images = df['count'].sum()
        self.product_ids = list(df['product_id'])
        self.ids = ids
        self.df  = df

        #save
        self.num_ids = num_ids
        self.num_images = num_images
        print('\tnum_ids    = %d'%(num_ids))
        print('\tnum_images = %d'%(num_images))
        print('\ttime = %0.2f min'%((timer() - start) / 60))
        print('')



    def get_image_set(self, index):
        #image = cv2.imread(self.img_files[index], 1)

        offset = self.df.iloc[index]['offset']
        length = self.df.iloc[index]['length']
        f = open(CDISCOUNT_DIR + '/bson/%s.bson'%self.bson, 'rb')
        f.seek(offset)
        item = f.read(length)
        item = bson.BSON.decode(item)
        f.close()

        images=[]
        for img in item['imgs']:
            image = cv2.imdecode(np.fromstring(img['picture'], dtype=np.uint8), -1)
            images.append(image)

        return images


    def __getitem__(self, index):
        images = self.get_image_set(index)

        if self.mode=='train':
            label = self.labels[index]
        elif self.mode=='test':
            label = None

        if self.transform is not None:
            return self.transform(images, label, index)

        return images, label, index


    def __len__(self):
        return self.num_ids




## check ## ----------------------------------------------------------
## https://github.com/hujie-frank/SENet
##   Random Mirror	True
##   Random Crop	8% ~ 100%
##   Aspect Ratio	3/4 ~ 4/3
##   Random Rotation -10° ~ 10°
##   Pixel Jitter	 -20 ~ 20  (shift)
##


def run_check_dataset():

    dataset = CDiscountImageSetDataset(
                                'train_id_v0_7019896', 'train', mode='train',
                                #'test_id_1768182', 'test', mode='test',
                                # 'debug_train_id_v0_5000', 'train', mode='train',
                                transform = None,)
    sampler = SequentialSampler(dataset)
    #sampler = RandomSampler(dataset)
    #sampler = ConstantSampler(dataset,[0]*1000)

    print('index, str(label), str(image.shape)')
    print('-----------------------------------')
    for n in iter(sampler):
        images, label, index = dataset[n]
        print('%09d %s %d x %s'%(index, str(label), len(images), str(images[0].shape)))
        image_show('image', np.hstack(images) )
        cv2.waitKey(0)

## processing ########################################################################

def train_bson_to_summary_cvs():

    bson_file = '/media/ssd/data/kaggle/cdiscount/__download__/train.bson'
    csv_file  = '/media/ssd/data/kaggle/cdiscount/__temp__/train_by_product_id.csv'

    start = timer()
    rows = {}
    with open(bson_file, 'rb') as f:
        offset = 0
        num_items = 0
        while True:
            item_length_bytes = f.read(4)
            if len(item_length_bytes) == 0:
                break

            length = struct.unpack('<i', item_length_bytes)[0]
            f.seek(offset)
            item = f.read(length)
            assert len(item) == length

            item = bson.BSON.decode(item)
            product_id = item['_id']
            count = len(item['imgs'])
            category_id = item['category_id']
            rows[product_id] = [count, category_id, offset, length]

            offset += length
            f.seek(offset)
            num_items += 1
            print('\rreading ...  %08d  '%product_id+str(rows[product_id]),end='',flush=True)

    print('')
    columns = ['count', 'category_id', 'offset', 'length']
    df = pd.DataFrame.from_dict(rows, orient='index')
    df.index.name = 'product_id'
    df.columns = columns

    df.to_csv(csv_file, index=True)
    num_images = df['count'].sum() #12371293 (train)
    num_ids = len(df.index)        #7069896

    print('\tnum_items  = %d'%num_items)
    print('\tnum_ids    = %d'%num_ids)
    print('\tnum_images = %d'%num_images)
    print('\ttime = %0.2f min'%((timer() - start) / 60))
    print('')


def test_bson_to_summary_cvs():

    bson_file = '/media/ssd/data/kaggle/cdiscount/__download__/test.bson'
    csv_file  = '/media/ssd/data/kaggle/cdiscount/__temp__/test_by_product_id.csv'

    start = timer()
    rows = {}
    with open(bson_file, 'rb') as f:
        offset = 0
        num_items = 0
        while True:
            item_length_bytes = f.read(4)
            if len(item_length_bytes) == 0:
                break

            length = struct.unpack('<i', item_length_bytes)[0]
            f.seek(offset)
            items = f.read(length)
            assert len(items) == length

            item = bson.BSON.decode(items)
            product_id = item['_id']
            count = len(item['imgs'])
            rows[product_id] = [count, offset, length]

            offset += length
            f.seek(offset)
            num_items += 1
            print('\rreading ...  %08d  '%product_id+str(rows[product_id]),end='',flush=True)

    print('')
    columns = ['count', 'offset', 'length']
    df = pd.DataFrame.from_dict(rows, orient='index')
    df.index.name = 'product_id'
    df.columns = columns

    df.to_csv(csv_file, index=True)
    num_images = df['count'].sum() #1768182 (test)
    num_ids = len(df.index)        #3095080

    print('\tnum_items  = %d'%num_items)
    print('\tnum_ids    = %d'%num_ids)
    print('\tnum_images = %d'%num_images)
    print('\ttime = %0.2f min'%((timer() - start) / 60))
    print('')
#

# main #################################################################
if __name__ == '__main__':
    print( '%s: calling main function ... ' % os.path.basename(__file__))
    #train_bson_to_summary_cvs()
    #test_bson_to_summary_cvs()

    run_check_dataset()

