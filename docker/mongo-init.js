const user = encodeURIComponent(process.env.MONGO_INITDB_ROOT_USERNAME);
const password = encodeURIComponent(process.env.MONGO_INITDB_ROOT_PASSWORD);
try {
    // The image's first-run setup uses a temporary local server. A ping may
    // succeed before that server is replaced by the final network listener.
    let admin = null;
    for (let attempt = 0; attempt < 30; attempt++) {
        try {
            const connection = new Mongo(`mongodb://${user}:${password}@mongodb:27017/?authSource=admin&directConnection=true&serverSelectionTimeoutMS=2000&connectTimeoutMS=2000`);
            const candidate = connection.getDB('admin');
            if (candidate.runCommand({ping: 1}).ok) {
                admin = candidate;
                break;
            }
        } catch (error) {
            // No driver error text: connection strings contain credentials.
        }
        sleep(1000);
    }
    if (admin === null) throw new Error('MongoDB unavailable');
    let status;
    try {
        status = admin.runCommand({replSetGetStatus: 1});
    } catch (error) {
        if (error.code !== 94) throw error;
        status = {ok: 0, code: 94};
    }
    if (!status.ok) {
        if (status.code !== 94) throw new Error('Unable to inspect replica set');
        const result = admin.runCommand({replSetInitiate: {_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]}});
        if (!result.ok) throw new Error('Unable to initialize replica set');
    }
    for (let attempt = 0; attempt < 60; attempt++) {
        if (admin.runCommand({hello: 1}).isWritablePrimary) {
            print('Replica set rs0 ready');
            quit(0);
        }
        sleep(1000);
    }
    throw new Error('Replica set primary unavailable');
} catch (error) {
    print('Replica set initialization failed. Check MongoDB configuration.');
    quit(1);
}
