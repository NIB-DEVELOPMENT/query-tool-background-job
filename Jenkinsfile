def remote = [:]
remote.name = 'devadmin'
remote.host = '192.168.100.123'
remote.allowAnyHosts = true


pipeline {
    agent any
    environment {
        DEV_CREDS = credentials('devadmin')
        DOCKER_CREDS = credentials('DockerHub')
    }
    stages {
        stage('Rebuild Background Image'){
            steps {
                    sh 'docker build -t nibitdev/query-tool-background-job:staging .'
                }
            }
        stage('Login to DockerHub'){
            steps {
                sh 'echo $DOCKER_CREDS_PSW | docker login -u $DOCKER_CREDS_USR --password-stdin'
            }
        }
        stage('Push Background Job Image'){
            steps {
                sh 'docker push nibitdev/query-tool-background-job:staging'
            }
        }
         stage('Remove Old Query Tool Background Job Containers'){
            steps {
                script {
                    remote.user = env.DEV_CREDS_USR 
                    remote.password = env.DEV_CREDS_PSW
                }
                sshCommand (remote: remote, command: """
                    cd ~/projects/deploy-query-tool
                    echo '${env.DEV_CREDS_PSW}' | sudo -S docker compose stop background-job
                    echo '${env.DEV_CREDS_PSW}' | sudo -S docker compose rm -f background-job
                    """)
                }
            }
        stage('Deploy New Query Tool Background Job Containers'){
            steps{
                script {
                    remote.user = env.DEV_CREDS_USR 
                    remote.password = env.DEV_CREDS_PSW
                }
                sshCommand (remote: remote, command: """
                    cd ~/projects/deploy-query-tool
                    echo '${env.DEV_CREDS_PSW}' | sudo -S docker compose up -d
                    """)
                }
            }
    }
        post {
            always {
                sh 'docker logout'
            }
        }
    }