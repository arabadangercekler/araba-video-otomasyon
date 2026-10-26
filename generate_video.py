name: Otomatik Video Üret

on:
  workflow_dispatch:
  schedule:
    - cron: '0 10 * * 1,4'

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Repo'yu indir
        uses: actions/checkout@v4

      - name: Python kur
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Gerekli paketleri yükle
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y -qq ffmpeg fonts-dejavu-core
          pip install -r requirements.txt

      - name: Video üret
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}
        run: python generate_video.py

      - name: Videoyu kaydet
        uses: actions/upload-artifact@v4
        with:
          name: uretilen-video
          path: video.mp4
          retention-days: 7
