FROM python:3.7.6-buster

RUN mkdir /pytest_mount/
RUN ls -ltr
COPY api/mockapi.py /pytest_mount/
COPY ./test-requirements.txt /pytest_mount/
COPY ./setup.py ./setup.py

RUN pip install --upgrade pip
RUN pip install -e .
RUN pip3 install -r /pytest_mount/test-requirements.txt

WORKDIR /pytest_mount/

CMD "pytest"
ENV PYTHONDONTWRITEBYTECODE=true
