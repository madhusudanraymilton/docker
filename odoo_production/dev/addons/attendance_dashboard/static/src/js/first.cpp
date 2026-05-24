#include <bits/stdc++.h>
using namespace std;






int main(){



    int t;

    cin>>t;

    while(t--){

        int n;

        cin>>n;

        vector<int> a(n);
       

        for (int i=0; i<n; i++){

            cin>>a[i];
        }

        int l = -1 ;
        for (int i=0; i<n; i++){

            if (a[i] == n ){

                l = i;

                break;;
            }
        }


        reverse(a.begin()+l , a.end());


        for (auto u: a) cout<<u<<" ";
        cout<<"\n";
    }



    return 0;
}