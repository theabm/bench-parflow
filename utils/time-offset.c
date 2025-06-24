#include <stdio.h>
#include <mpi.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char** argv){
    int rank, size;
    MPI_Init(&argc, &argv);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    
    struct timespec mytime;
    clock_gettime(CLOCK_REALTIME, &mytime);
    double time_sec = mytime.tv_sec + mytime.tv_nsec / 1000000000.0;
    
    char hostname[256];
    gethostname(hostname, sizeof(hostname));
    
    printf("[SCRIPT] TIME : %f RANK : %d HOSTNAME : %s\n", time_sec, rank, hostname);
    
    MPI_Finalize();  // This was missing!
    return 0;
}