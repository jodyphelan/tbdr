# syntax=docker/dockerfile:1
FROM mambaorg/micromamba:1.5.8-jammy

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV MAMBA_DOCKERFILE_ACTIVATE=${MAMBA_DOCKERFILE_ACTIVATE}
ENV TBDR_UPLOAD_DIR=/data/uploads \
    TBDR_RESULTS_DIR=/opt/tbdr/tbdr/static/results \
    TBDR_TBPROFILER_DB=who_v3 \
    TBDR_TBPROFILER_DB_DIR=/opt/conda/envs/tbdr/share/tbprofiler

USER root
RUN mkdir -p /opt/tbdr /data/uploads
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
USER $MAMBA_USER
RUN micromamba create --yes --name tbdr --file /tmp/environment.yml \
    && micromamba clean --all --yes
ENV PATH=/opt/conda/envs/tbdr/bin:$PATH \
    CONDA_DEFAULT_ENV=tbdr \
    MAMBA_DEFAULT_ENV=tbdr

WORKDIR /opt/tbdr
COPY --chown=$MAMBA_USER:$MAMBA_USER . /opt/tbdr
RUN mkdir -p /opt/conda/envs/tbdr/share/tbprofiler \
    && python -m pip install --no-deps . \
    && cd /tmp \
    && pip install --force-reinstall git+https://github.com/jodyphelan/TBProfiler.git@dev \
    && pip install --force-reinstall git+https://github.com/jodyphelan/pathogen-profiler.git@dev \
    && pip install --force-reinstall git+https://github.com/jodyphelan/is6110.git \
    && tb-profiler load_library /opt/tbdr/who_v3 \
        --db_dir /opt/conda/envs/tbdr/share/tbprofiler --force

USER root
RUN mkdir -p /opt/tbdr/tbdr/static/results /data/uploads \
    && touch /opt/tbdr/tbdr/static/results/.gitkeep \
    && chown -R $MAMBA_USER:$MAMBA_USER /opt/tbdr /data/uploads \
    /opt/conda/envs/tbdr/share/tbprofiler

EXPOSE 8000
USER $MAMBA_USER
