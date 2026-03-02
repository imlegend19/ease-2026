FROM rocker/r2u:24.04

RUN Rscript -e "options(repos='https://cloud.r-project.org'); install.packages('ScottKnottESD')"

WORKDIR /work
