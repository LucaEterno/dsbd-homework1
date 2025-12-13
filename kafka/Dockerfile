FROM confluentinc/cp-kafka:7.4.0
USER root
COPY topic_setup.sh /usr/local/bin/topic_setup.sh
RUN chmod +x /usr/local/bin/topic_setup.sh
CMD [ "/bin/bash", "/usr/local/bin/topic_setup.sh" ]