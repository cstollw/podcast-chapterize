from google.cloud import storage
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import wget
import os
import json
import uuid

bucket_name = 'transcribe-buffer'

def transcribeAudioFromUrl(url):
    os.system('export GOOGLE_APPLICATION_CREDENTIALS="/home/lukas/Documents/cred.json"')
    filename = str(uuid.uuid1()) + os.path.basename(url)
    wget.download(url, out='transcribe/download/' + filename)
    rawPath = os.path.join('transcribe/download', filename)
    print('\ndownloaded file {0}'.format(rawPath))
    path = toWav(rawPath)
    gcsUri = uploadToGoogleCloud(path)
    transcriptFile = transcribeBlob(gcsUri)
    deleteBlob(gcsUri)
    return {
        'originalAudioFilePath': rawPath,
        'wavAudioFilePath': path,
        'gcsUri': gcsUri,
        'transcriptFile': transcriptFile
    }

def uploadToGoogleCloud(filepath):
    print('\nupload file {0} to google cloud bucket'.format(filepath))
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(os.path.basename(filepath))
    blob.upload_from_filename(filepath)

    return 'gs://' + bucket_name + '/' + os.path.basename(filepath)

def deleteBlob(gcs_uri):
    blob_name = os.path.basename(gcs_uri)
    print('\ndelete file {0} from google cloud bucket'.format(blob_name))
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)

    blob.delete()

def toWav(path):
    filename = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join('transcribe/download', filename) + '.wav'
    cmd = 'ffmpeg -y -i {0} -vn -ac 1 -acodec pcm_s16le -ar 16000 {1}'.format(path, dest)
    print('\nconvert file {0} to wav format'.format(path))
    os.system(cmd)
    return dest

def transcribeBlob(gcs_uri):
    print('\ntranscribe blob {0}'.format(gcs_uri))
    # transcribe audio file with google speech api
    client = speech.SpeechClient()

    audio = types.RecognitionAudio(uri=gcs_uri)
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code='en-US',
        enable_word_time_offsets=True
        )

    operation = client.long_running_recognize(config, audio)

    print('Waiting for transcription to complete...')
    response = operation.result(timeout=10000)

    utterances = []
    words = []
    for result in response.results:
        print(u'Transcript: {}'.format(result.alternatives[0].transcript))
        print('Confidence: {}'.format(result.alternatives[0].confidence))
        for word in result.alternatives[0].words:
            w = {}
            w['word'] = word.word
            w['startTime'] = word.start_time.seconds + (word.start_time.nanos / 1000000000)
            words.append(w)
        utterances.append(words)
        words = []
        
    with open('output/' + os.path.basename(gcs_uri) + '_transcript.json', 'w') as f:
        json.dump(utterances, f)

    return 'output/' + os.path.basename(gcs_uri) + '_transcript.json'